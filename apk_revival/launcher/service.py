"""V2 application service: all buttons call real V1 operations."""
from __future__ import annotations
import hashlib,json,pathlib,re,threading,zipfile,sys,os
from ..analysis import analyze,markdown
from ..adapters import adapter
from ..exporter import export_game
from ..restoration import Restorer
from ..saves import Saves
from ..util import RevivalError,atomic_json,digest,now,read_json
from ..verification import verify
from .jobs import Jobs
from .runtime_setup import RuntimeManager,ManagedAndroid
from .tools_setup import configure,health

class Launcher:
    def __init__(self,store):
        self.store=store;self.jobs=Jobs();self.runtime_manager=RuntimeManager();self.android=None;self.active=None;self.runtime_factory=ManagedAndroid;configure()
        file=store.root/'launcher-settings.json';self.settings=read_json(file) if file.exists() else {'schema_version':1,'serial':None,'fullscreen':False,'verify_after_prepare':True}
    def save_settings(self):atomic_json(self.store.root/'launcher-settings.json',self.settings)
    def import_game(self,apk,support,ctx):
        ctx.step('Checking game files');p=self.store.import_game(apk,support);ctx.step('Analyzing dependencies');p=analyze(self.store,p['id'])
        title=p['analysis']['metadata']['application'].get('label')
        if p['analysis']['fixture']:p['title']='Tap Quest'
        elif p.get('adapter')=='meego-1.32':p['title']='The Meego'
        elif title and not title.startswith('@'):p['title']=title[:100]
        p.setdefault('launcher',{}).setdefault('launch_checks',[]);self.store.save(p);return p
    def attach(self,game,support,ctx):
        if self.active and self.active['game']==game:raise RevivalError('Stop this game before changing its supporting files.')
        ctx.step('Checking supporting files');self.store.attach(game,support);ctx.step('Analyzing dependencies');return analyze(self.store,game)
    def prepare(self,game,path,ctx):
        if self.active:raise RevivalError('Stop the running game before preparation.')
        p=self.store.load(game)
        if not p['analysis']:ctx.step('Analyzing dependencies');p=analyze(self.store,game)
        if not p.get('adapter'):raise RevivalError('This game needs a game-specific restoration adapter. Export Diagnostics to share its evidence report.')
        path=path or p['analysis']['recommended_path']
        # Prepare is idempotent. A valid saved artifact (or completed independent
        # rebuild) is reused on every restart, without re-signing or touching saves.
        previous=p.get('restoration',{})
        if previous.get('path')==path:
            if path=='rebuild' and p.get('rebuild',{}).get('feasibility'):
                ctx.step('Using the already prepared rebuild');return p
            artifact=previous.get('artifact')
            if artifact:
                prepared=self.store.directory(game)/artifact
                if prepared.is_file() and digest(prepared)==previous.get('artifact_sha256'):
                    ctx.step('Using the already prepared game');return p
        if path!='rebuild' and not health()['preparation_ready']:raise RevivalError('Preparation tools are missing. Open Setup and select Install preparation tools.')
        ctx.step('Reviewing restoration plan');Restorer(self.store).plan(game,path);p=Restorer(self.store).prepare(game,path,progress=ctx.step)
        p.setdefault('launcher',{})['prepared_at']=now();self.store.save(p)
        if path=='rebuild':ctx.skipped('Testing original APK offline','A separate rebuild cannot verify the original APK.');return p
        ctx.step('Checking launch compatibility')
        info=self.runtime_manager.discover()
        if not info['ready']:
            ctx.skipped('Testing offline play','Android is not connected. The APK is prepared; complete runtime setup to test it.');return self.store.load(game)
        serial=self.runtime_manager.ensure(self.settings.get('serial'));p['runtime']['serial']=serial;self.store.save(p)
        self.runtime_factory(serial).compatible(p)
        if p.get('adapter')=='meego-1.32':ctx.skipped('Testing offline play','Meego requires a guided Android gameplay test. Signing and host service tests do not certify the game.');return self.store.load(game)
        if self.settings.get('verify_after_prepare',True):
            ctx.step('Testing offline play');result=verify(self.store,game)
            if not result['passed']:ctx.skipped('Offline verification incomplete',result.get('error','Some gameplay checks did not pass.'))
        return self.store.load(game)
    def play(self,game,ctx):
        if self.active:raise RevivalError('A game is already running. Stop it first.')
        p=self.store.load(game)
        if not p.get('adapter'):raise RevivalError('This game is not supported by a restoration adapter yet.')
        if p['restoration']['path']=='rebuild':
            if not p['rebuild'].get('feasibility'):raise RevivalError('Prepare the rebuild first.')
            self.active={'game':game,'kind':'rebuild','started_at':now()};return self.active
        artifact=p.get('restoration',{}).get('artifact')
        expected=p.get('restoration',{}).get('artifact_sha256')
        if not artifact or not expected:raise RevivalError('This game is not prepared. Choose Prepare game first.')
        prepared=self.store.directory(game)/artifact
        if not prepared.is_file() or digest(prepared)!=expected:
            raise RevivalError('The prepared game file is missing or changed. Choose Prepare game to repair it. Your saves are preserved.')
        ctx.step('Connecting Android');serial=self.runtime_manager.ensure(self.settings.get('serial'));p['runtime']['serial']=serial;self.store.save(p)
        ctx.step('Checking game compatibility');runtime=self.runtime_factory(serial);runtime.compatible(p);self.android=runtime
        try:
            ctx.step('Installing the prepared client if needed');runtime.install(self.store,p)
            if p['restoration']['path']=='local_backend':ctx.step('Starting local services');runtime.start_backend(self.store,p)
            ctx.step('Launching the game');runtime.launch(p)
            self.active={'game':game,'kind':'android','started_at':now(),'serial':serial}
            p=self.store.load(game);p.setdefault('launcher',{}).setdefault('launch_checks',[]).append({'kind':'android_activity','time':now(),'artifact_sha256':p['restoration']['artifact_sha256'],'serial':serial,'offline_gameplay_verified':False})
            self.store.save(p);return self.active
        except Exception:
            try:runtime.stop()
            finally:self.android=None;self.active=None
            raise
    def stop(self,ctx=None):
        if ctx:ctx.step('Stopping the selected game')
        try:
            if self.android:self.android.stop()
        finally:self.android=None;self.active=None
        return {'stopped':True}
    def monitor(self):
        if not self.android or not self.active:return None
        try:
            if self.android.backend and not self.android.backend.thread.is_alive():raise RevivalError('The local backend stopped. Stop the session and retry Play.')
            pid=self.android.shell('pidof',self.android.package,timeout=6).strip()
            if pid:return None
            message='The game has closed.'
        except RevivalError as e:message='Android disconnected or the game closed: '+str(e)
        try:self.stop()
        except RevivalError:pass
        return message
    def backup(self,game,ctx):
        ctx.step('Backing up progress');return Saves(self.store).backup(game)
    def restore(self,game,backup,ctx):
        self.stop();ctx.step('Preserving the current save and restoring backup');return Saves(self.store).restore(game,backup)
    def export(self,game,output,ctx):
        ctx.step('Checking and packaging the game');result=export_game(self.store,game,output)
        if not getattr(sys,'frozen',False):return result
        ctx.step('Adding the native portable launcher')
        output=pathlib.Path(output);staged=output.with_suffix('.native.tmp');app=pathlib.Path(sys.executable).resolve().parent
        try:
            with zipfile.ZipFile(output) as original,zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED) as native:
                hashes={}
                for i in original.infolist():
                    if i.filename in {'hashes.json','README.md'}:continue
                    data=original.read(i.filename);native.writestr(i,data);hashes[i.filename]=hashlib.sha256(data).hexdigest()
                files=[app/'APK-Revival']+sorted((app/'_internal').rglob('*'))
                for file in files:
                    if not file.is_file() or file.name=='tapquest-original.apk':continue
                    ctx.check();name='Play-Game' if file==app/'APK-Revival' else str(file.relative_to(app));native.write(file,name);hashes[name]=digest(file)
                text='APK Revival portable game\n\nExtract this ZIP and double-click Play-Game. If executable permission was removed by your archive tool, enable it through Properties > Permissions. No Python installation is needed. Android exports still require Waydroid and connection tools. The separate rebuild needs no Android runtime. Private saves are not included; new portable saves remain in ~/.local/share/apk-revival/portable-saves/.\n\nStatus is recorded in profile.json. A successful launch is not offline gameplay verification.\n'
                native.writestr('START-HERE.txt',text);hashes['START-HERE.txt']=hashlib.sha256(text.encode()).hexdigest();native.writestr('hashes.json',json.dumps(hashes,indent=2))
            staged.replace(output);p=self.store.load(game);p['restoration']['export']={'path':str(output),'sha256':digest(output),'native_launcher':True};self.store.save(p);result.update(sha256=digest(output),native_launcher=True);return result
        finally:
            if staged.exists():staged.unlink()
    def verify(self,game,ctx):
        self.stop();serial=self.runtime_manager.ensure(self.settings.get('serial'));p=self.store.load(game);p['runtime']['serial']=serial;self.store.save(p);ctx.step('Testing offline play');return verify(self.store,game)
    def diagnostics(self,game,output,ctx):
        ctx.step('Collecting the evidence report');p=self.store.load(game)
        # Summary only: no APKs, assets, secrets, saves or raw imported logs.
        report={'schema_version':1,'version':'0.2.0','apk_sha256':p['apk_sha256'],'apk_version':p['apk_version'],'status':p['status'],'analysis':p['analysis'],'restoration_path':p['restoration']['path'],'verification':p['verification'],'runtime':self.runtime_manager.last,'job_history':[j.snapshot() for j in self.jobs.history[-20:]]}
        text=json.dumps(report,indent=2)
        text=text.replace(str(pathlib.Path.home()),'<HOME>').replace(str(self.store.root),'<DATA>')
        text=re.sub(r'(?i)(token|password|authorization|api[_-]?key)(["\s:=]+)[^\s,"}]+',r'\1\2<REDACTED>',text)
        dest=pathlib.Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('diagnostics.json',text);z.writestr('README.txt','APK Revival diagnostics. Original games, assets, private saves, signing keys and raw logs are excluded. Review the summary before sharing.\n')
        return {'file':str(dest)}
    def shutdown(self):
        try:self.stop()
        finally:self.runtime_manager.stop_owned_session()
