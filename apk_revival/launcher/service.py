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
        self.store=store;self.jobs=Jobs(store.root/'job-logs');self.runtime_manager=RuntimeManager(store.root/'runtime-state.json');self.android=None;self.active=None;self.connection_failures=0;self.runtime_factory=ManagedAndroid;configure()
        file=store.root/'launcher-settings.json';self.settings=read_json(file) if file.exists() else {'schema_version':1,'serial':None,'fullscreen':False,'verify_after_prepare':True}
    def save_settings(self):atomic_json(self.store.root/'launcher-settings.json',self.settings)
    def import_game(self,apk,support,ctx):
        ctx.step('Checking game files');p=self.store.import_game(apk,support);ctx.step('Analyzing dependencies');p=analyze(self.store,p['id'])
        from .apk_info import inspect_apk
        p.setdefault('launcher',{})['apk']=inspect_apk(self.store.base(p),self.store.directory(p['id']))
        from .metadata import resolve_label
        title=p['launcher']['apk'].get('label') or resolve_label(self.store.base(p),p['analysis']['metadata']['application'].get('label'))
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
        client_current=True
        if p.get('adapter')=='meego-1.32':
            from ..meego import camera
            client_current=camera.prepared(previous,p['runtime'].get('meego_timer_hz',60))
        if previous.get('path')==path and client_current:
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
        direct=not p.get('restoration',{}).get('artifact') and p['restoration']['path']!='rebuild'
        if direct:return self.play_original(p,ctx)
        if p['restoration']['path']=='rebuild':
            if not p['rebuild'].get('feasibility'):raise RevivalError('Prepare the rebuild first.')
            self.active={'game':game,'kind':'rebuild','started_at':now()}
            p.setdefault('launcher',{})['last_played']=self.active['started_at'];self.store.save(p);return self.active
        artifact=p.get('restoration',{}).get('artifact')
        expected=p.get('restoration',{}).get('artifact_sha256')
        if not artifact or not expected:raise RevivalError('This game is not prepared. Choose Prepare game first.')
        prepared=self.store.directory(game)/artifact
        if not prepared.is_file() or digest(prepared)!=expected:
            raise RevivalError('The prepared game file is missing or changed. Choose Prepare game to repair it. Your saves are preserved.')
        ctx.step('Starting the game runtime');serial=self.runtime_manager.ensure(progress=ctx.step);p['runtime']['serial']=serial;self.store.save(p)
        ctx.step('Checking game compatibility');runtime=self.runtime_factory(serial);runtime.compatible(p);self.android=runtime;runtime.launch_progress=ctx.step
        try:
            p=self.prepare_meego_camera(p,runtime,ctx)
            ctx.step('Installing the prepared client if needed');runtime.install(self.store,p)
            if p['restoration']['path']=='local_backend':ctx.step('Starting local services');runtime.start_backend(self.store,p)
            ctx.step('Launching the game');runtime.launch(p)
            self.active={'game':game,'kind':'android','started_at':now(),'serial':serial}
            p=self.store.load(game);p.setdefault('launcher',{}).setdefault('launch_checks',[]).append({'kind':'android_activity','time':now(),'artifact_sha256':p['restoration']['artifact_sha256'],'serial':serial,'offline_gameplay_verified':False});p['launcher']['last_played']=self.active['started_at']
            self.store.save(p);return self.active
        except Exception:
            try:
                try:ctx.step('Launch failed; releasing game connections')
                except Exception:pass
                try:runtime.stop()
                except Exception:pass
            finally:self.android=None;self.active=None
            raise
    def prepare_meego_camera(self,p,runtime,ctx):
        """Upgrade stale Meego clients once, selecting timing from this guest.

        Called only by normal Play after runtime readiness. Preparation uses
        the existing signing identity and immutable original; Android install
        still uses -r. No save import/reset or gameplay verification occurs.
        """
        if p.get('adapter')!='meego-1.32':return p
        from ..meego import camera,frame_pacing
        ctx.step('Reading the active game display')
        try:
            hz=frame_pacing.active_timer_hz(runtime.shell('dumpsys','display',timeout=5))
        except RevivalError:
            hz=60
        if camera.prepared(p.get('restoration',{}),hz):return p
        if not health()['preparation_ready']:
            raise RevivalError('Meego needs its camera client update, but preparation tools are missing. Open Setup and select Install preparation tools. The previous APK and saves are preserved.')
        ctx.step('Preparing the Meego camera update ('+str(hz)+' Hz)')
        p['runtime']['meego_timer_hz']=hz;self.store.save(p)
        # Restorer keeps the previous working artifact if preparation fails;
        # successful preparation records the revision/rate in the signed plan.
        p=Restorer(self.store).prepare(p['id'],p['restoration']['path'],progress=ctx.step)
        p.setdefault('launcher',{})['prepared_at']=now();self.store.save(p)
        return p
    def play_original(self,p,ctx):
        ctx.step('Starting the game runtime');serial=self.runtime_manager.ensure(progress=ctx.step)
        runtime=self.runtime_factory(serial)
        ctx.step('Checking architecture and Android version');runtime.compatible(p)
        self.android=runtime;runtime.launch_progress=ctx.step
        try:
            ctx.step('Installing APK without removing game data');runtime.install(self.store,p,original=True)
            ctx.step('Opening the game');runtime.launch(p)
            self.active={'game':p['id'],'kind':'android','started_at':now(),'serial':serial}
            p.setdefault('launcher',{}).setdefault('launch_checks',[]).append({'kind':'original_activity','time':now(),'apk_sha256':p['apk_sha256'],'offline_gameplay_verified':False})
            self.store.save(p);return self.active
        except Exception:
            try:
                try:ctx.step('Launch failed; releasing game connections')
                except Exception:pass
                try:runtime.stop()
                except Exception:pass
            finally:self.android=None;self.active=None
            raise
    def stop(self,ctx=None):
        if ctx:ctx.step('Stopping the selected game')
        try:
            if self.android:self.android.stop()
        finally:
            try:
                if ctx:ctx.step('Closing the game runtime started by APK Revival')
                self.runtime_manager.stop_owned_session()
            finally:self.android=None;self.active=None;self.connection_failures=0
        return {'stopped':True}
    def mod_state(self, game):
        p = self.store.load(game)
        if p.get('adapter') != 'meego-1.32':
            raise RevivalError('Skip timer is currently available for Meego only.')
        if not self.active or self.active['game'] != game:
            raise RevivalError('Press Play on this Meego entry before using Mods.')
        state = getattr(getattr(getattr(self.android, 'backend', None), 'server', None), 'state', None)
        if state is None:
            raise RevivalError('The local Meego service is unavailable. Stop the game and press Play again.')
        return state
    def mod_timers(self, game):
        return self.mod_state(game).mod_timers()
    def skip_timer(self, game, token, ctx):
        ctx.step('Skipping only the selected timer')
        return self.mod_state(game).skip_timer(token)
    def monitor(self):
        if not self.android or not self.active:return None
        if self.android.backend and not self.android.backend.thread.is_alive():
            try:self.stop()
            except RevivalError:pass
            return 'The local game service stopped. Play again to recover it.'
        try:
            pid=self.android.shell('pidof',self.android.package,timeout=6).strip()
            if pid:
                self.connection_failures=0
                state=getattr(getattr(self.android.backend,'server',None),'state',None)
                notice=state.take_action_notice() if state and hasattr(state,'take_action_notice') else None
                return 'Game action: '+notice if notice else None
            message='The game has closed.'
        except RevivalError as e:
            from .connection_recovery import recover
            result=recover(self.runtime_manager,self.android,self.active)
            if result['state']=='recovered':self.connection_failures=0;return 'Reconnected to the game runtime.'
            if result['state']=='paused':self.connection_failures=0;return result['detail']
            self.connection_failures+=1
            if self.connection_failures<3:return f'Reconnecting to the game runtime ({self.connection_failures}/3): '+result['detail']
            message='The game runtime could not reconnect after three checks: '+result['detail']
        try:self.stop()
        except RevivalError:pass
        return message
    def backup(self,game,ctx):
        ctx.step('Backing up progress');return Saves(self.store).backup(game)
    def new_meego_village(self,game,ctx):
        p=self.store.load(game)
        if p.get('adapter')!='meego-1.32' or p['restoration']['path']!='local_backend':raise RevivalError('Prepare Meego before creating a village.')
        if self.active and self.active['game']!=game:raise RevivalError('Stop the other running game first.')
        from ..meego.backend import config_path
        from ..meego.engine.server import initial_village
        from ..saves import validate_meego_save
        config=config_path(self.store,p)
        seed=read_json(config/'starter-packet.json')
        fresh=initial_village(seed,rules=read_json(config/'local-rules.json'));validate_meego_save(fresh)
        self.stop(ctx)
        save=self.store.directory(game)/'saves/village.json'
        backup=None
        if save.exists():
            ctx.step('Backing up the previous village');backup=Saves(self.store).backup(game)
        ctx.step('Creating a fresh village without bonus supplies or skulls')
        atomic_json(save,fresh)
        return {'created':True,'previous_backup':backup,'starting_villagers':len(fresh['game_state']['all_villagers']),
                'original_defaults_verified':False}
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
        from .. import __version__
        self.store.games()
        # Summary only: no APKs, assets, secrets, saves or raw imported logs.
        report={'schema_version':1,'version':__version__,'apk_sha256':p['apk_sha256'],'apk_version':p['apk_version'],'status':p['status'],'analysis':p['analysis'],'restoration_path':p['restoration']['path'],'verification':p['verification'],'runtime':self.runtime_manager.last,'library_errors':self.store.last_library_errors,'job_history':[j.snapshot() for j in self.jobs.history[-20:]]}
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

