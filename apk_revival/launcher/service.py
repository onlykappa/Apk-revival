"""V2 application service: all buttons call real V1 operations."""
from __future__ import annotations
import calendar,hashlib,json,pathlib,re,threading,time,uuid,zipfile,sys,os
from ..analysis import analyze,markdown
from ..adapters import adapter,find,load_plugins
from ..exporter import export_game
from ..restoration import Restorer
from ..saves import Saves
from ..util import RevivalError,atomic_json,digest,now,read_json
from ..verification import verify
from ..netproxy import summary as server_summary
from .jobs import Jobs
from .runtime_setup import RuntimeManager,ManagedAndroid
from .tools_setup import configure,health

# Monitor checks run every 5 seconds: about 15 seconds off screen ends the game.
OFFSCREEN_LIMIT=3
def host_saves(p):
    """True when a restoration adapter keeps this game's progress in host files."""
    from ..saves import host_save_plugin
    return p.get('adapter')=='tapquest-v1' or host_save_plugin(p) is not None

class Launcher:
    def __init__(self,store):
        load_plugins(store.root/'plugins')
        self.store=store;self.jobs=Jobs(store.root/'job-logs');self.runtime_manager=RuntimeManager(store.root/'runtime-state.json');self.android=None;self.active=None;self.connection_failures=0;self.offscreen_checks=0;self.network=None;self.runtime_factory=ManagedAndroid;configure()
        file=store.root/'launcher-settings.json';self.settings=read_json(file) if file.exists() else {'schema_version':1,'serial':None,'fullscreen':False,'verify_after_prepare':True}
    def save_settings(self):atomic_json(self.store.root/'launcher-settings.json',self.settings)
    def import_game(self,apk,support,ctx):
        ctx.step('Checking game files');p=self.store.import_game(apk,support);ctx.step('Analyzing dependencies');p=analyze(self.store,p['id'])
        from .apk_info import inspect_apk
        p.setdefault('launcher',{})['apk']=inspect_apk(self.store.base(p),self.store.directory(p['id']))
        from .metadata import resolve_label
        title=p['launcher']['apk'].get('label') or resolve_label(self.store.base(p),p['analysis']['metadata']['application'].get('label'))
        if p['analysis']['fixture']:p['title']='Tap Quest'
        elif find(p) is not None and getattr(find(p),'title',None):p['title']=find(p).title
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
        plugin=find(p)
        client_current=plugin.prepared_current(previous,p) if hasattr(plugin,'prepared_current') else True
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
        self.check_compatible(self.runtime_factory(serial),p)
        if getattr(plugin,'verify_note',None):ctx.skipped('Testing offline play',plugin.verify_note);return self.store.load(game)
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
        ctx.step('Checking game compatibility');runtime=self.runtime_factory(serial);self.check_compatible(runtime,p);self.android=runtime;runtime.launch_progress=ctx.step
        try:
            p=self.before_play(p,runtime,ctx)
            ctx.step('Installing the prepared client if needed');runtime.install(self.store,p)
            if p['restoration']['path']=='local_backend':ctx.step('Starting local services');runtime.start_backend(self.store,p)
            self.start_network(p,runtime,ctx);self.start_display(p,runtime,ctx);self.clear_crash_buffer(runtime)
            ctx.step('Launching the game');runtime.launch(p)
            self.active={'game':game,'kind':'android','started_at':now(),'serial':serial}
            p=self.store.load(game);p.setdefault('launcher',{}).setdefault('launch_checks',[]).append({'kind':'android_activity','time':now(),'artifact_sha256':p['restoration']['artifact_sha256'],'serial':serial,'offline_gameplay_verified':False});p['launcher']['last_played']=self.active['started_at']
            self.store.save(p);return self.active
        except Exception:
            try:
                try:ctx.step('Launch failed; releasing game connections')
                except Exception:pass
                self.release_game_settings()
                try:self.capture_crash(p['id'],runtime,'The game failed to start.')
                except Exception:pass
                try:runtime.stop()
                except Exception:pass
            finally:self.android=None;self.active=None
            raise
    def release_game_settings(self):
        """Undo network and display changes. Never raises: Stop must always finish."""
        for step in (self.stop_network,self.stop_display):
            try:step()
            except Exception:pass  # Leftovers are undone before the next Play.
    def start_display(self,p,runtime,ctx):
        """Apply the game's display settings, after undoing any left by a crash."""
        from .. import display
        self.display_runtime=runtime
        leftover=self.settings.get('display_restore')
        if leftover:
            try:display.restore(runtime,leftover)
            except RevivalError:pass
            self.settings['display_restore']=None;self.save_settings()
        if display.settings(p)!={'size':'default','landscape':False}:ctx.step('Applying display settings')
        def remember(previous):self.settings['display_restore']=previous;self.save_settings()
        display.apply(runtime,p,remember)
    def stop_display(self):
        from .. import display
        previous=getattr(self,'settings',{}).get('display_restore');runtime=getattr(self,'display_runtime',None)
        if not previous or runtime is None:return
        try:display.restore(runtime,previous);self.settings['display_restore']=None;self.save_settings()
        except RevivalError:pass  # Restored before the next Play instead.
    def network_log(self,game):return self.store.directory(game)/'network-log.jsonl'
    def start_network(self,p,runtime,ctx):
        """Apply the game's network setting; anything left from a crash is undone first."""
        from .. import game_network
        from ..android_saves import package_for
        if self.settings.get('network_applied'):
            game_network.clear_proxy(runtime);game_network.remove_leftovers(runtime)
            self.settings['network_applied']=False;self.save_settings()
        chosen=game_network.mode(p);self.network=None
        if chosen=='normal':return
        ctx.step('Applying network setting: '+game_network.LABELS[chosen])
        state={'runtime':runtime,'proxy':None,'uid':None}
        self.settings['network_applied']=True;self.save_settings();self.network=state
        try:
            if chosen in ('log','offline'):
                from ..netproxy import Proxy
                state['proxy']=Proxy(self.network_log(p['id']),'offline' if chosen=='offline' else 'log').start()
                game_network.set_proxy(runtime,state['proxy'].port)
            if chosen in ('offline','block'):
                state['uid']=game_network.package_uid(runtime,package_for(p));game_network.block(runtime,state['uid'])
        except Exception:
            self.stop_network();raise
    def stop_network(self):
        state=getattr(self,'network',None);self.network=None
        if not state:return
        from .. import game_network
        runtime=state['runtime']
        try:
            if state['proxy']:game_network.clear_proxy(runtime,state['proxy'].port)
            if state['uid'] is not None:game_network.unblock(runtime,state['uid'])
            self.settings['network_applied']=False;self.save_settings()
        except RevivalError:pass  # Cleaned up before the next Play instead.
        finally:
            if state['proxy']:state['proxy'].stop()
    def check_compatible(self,runtime,p):
        """Check the game against Android and remember Android's ARM support for the library."""
        try:return runtime.compatible(p)
        finally:
            status=getattr(runtime,'arm_status',None)
            if isinstance(status,dict) and status.get('known'):self.settings['android_arm']=status;self.save_settings()
    def check_arm(self,ctx):
        """Start Android if needed and read its ARM support."""
        from .. import arm_support
        runtime=self.android_runtime(ctx);ctx.step('Reading Android processor support');report=runtime.probe()
        if not report.get('available'):raise RevivalError('Android is not connected. '+report.get('error','Start Android from Setup and try again.'))
        status=arm_support.android_status(report.get('abis'),report.get('native_bridge'))
        self.settings['android_arm']=status;self.save_settings();return status
    def before_play(self,p,runtime,ctx):
        """Let the game's plugin update its prepared client once Android is ready."""
        plugin=find(p)
        return plugin.before_play(self,p,runtime,ctx) if hasattr(plugin,'before_play') else p
    def play_original(self,p,ctx):
        ctx.step('Starting the game runtime');serial=self.runtime_manager.ensure(progress=ctx.step)
        runtime=self.runtime_factory(serial)
        ctx.step('Checking architecture and Android version');self.check_compatible(runtime,p)
        self.android=runtime;runtime.launch_progress=ctx.step
        try:
            ctx.step('Installing APK without removing game data');runtime.install(self.store,p,original=True)
            self.start_network(p,runtime,ctx);self.start_display(p,runtime,ctx);self.clear_crash_buffer(runtime)
            ctx.step('Opening the game');runtime.launch(p)
            self.active={'game':p['id'],'kind':'android','started_at':now(),'serial':serial}
            p.setdefault('launcher',{}).setdefault('launch_checks',[]).append({'kind':'original_activity','time':now(),'apk_sha256':p['apk_sha256'],'offline_gameplay_verified':False})
            self.store.save(p);return self.active
        except Exception:
            try:
                try:ctx.step('Launch failed; releasing game connections')
                except Exception:pass
                self.release_game_settings()
                try:self.capture_crash(p['id'],runtime,'The game failed to start.')
                except Exception:pass
                try:runtime.stop()
                except Exception:pass
            finally:self.android=None;self.active=None
            raise
    def stop(self,ctx=None):
        if ctx:ctx.step('Stopping the selected game')
        self.record_playtime()
        try:
            if self.android:
                try:self.release_game_settings()
                finally:self.android.stop()
        finally:
            try:
                if ctx:ctx.step('Closing the game runtime started by APK Revival')
                self.runtime_manager.stop_owned_session()
            finally:self.android=None;self.active=None;self.connection_failures=0;self.offscreen_checks=0
        return {'stopped':True}
    def crash_logs(self,game):
        folder=self.store.directory(game)/'crash-logs'
        return sorted(folder.glob('*.txt'),reverse=True) if folder.is_dir() else []
    def clear_crash_buffer(self,runtime):
        try:runtime.adb('logcat','-b','crash','-c',timeout=5)
        except Exception:pass  # Not every Android allows clearing; capture filters by package anyway.
    def capture_crash(self,game,runtime,reason):
        """Save Android crash records that name this game; returns the file or None."""
        try:return self._capture_crash(game,runtime,reason)
        except Exception:return None  # A crash log must never get in the way of stopping a game.
    def _capture_crash(self,game,runtime,reason):
        from ..android_saves import package_for
        p=self.store.load(game,check=False);package=getattr(runtime,'package',None) or package_for(p)
        crash=runtime.adb('logcat','-d','-b','crash','-v','threadtime',timeout=10)
        main=runtime.adb('logcat','-d','-t','400','-v','threadtime',timeout=10)
        markers=('FATAL EXCEPTION','Fatal signal','AndroidRuntime','DEBUG  ','UnsatisfiedLinkError','dlopen failed','ANR in')
        lines=[l for l in crash.splitlines() if l.strip()]
        related=[l for l in main.splitlines() if package in l or any(m in l for m in markers)]
        if not any(package in l for l in lines+related):return None
        folder=self.store.directory(game)/'crash-logs';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(now().replace(':','-')+'.txt')
        path.write_text(f'APK Revival crash log\nGame: {p["title"]} ({package})\nWhen: {now()}\nWhat happened: {reason}\n\n== Android crash buffer ==\n'+'\n'.join(lines[-300:])+'\n\n== Related log lines ==\n'+'\n'.join(related[-150:])+'\n')
        for old in self.crash_logs(game)[20:]:old.unlink(missing_ok=True)
        return path
    def record_playtime(self):
        """Add the finished session to the game's total play time."""
        active=self.active
        if not active or not active.get('started_at') or not active.get('game'):return
        try:
            started=calendar.timegm(time.strptime(active['started_at'],'%Y-%m-%dT%H:%M:%SZ'))
            seconds=max(0,min(24*3600,int(time.time()-started)))
            p=self.store.load(active['game'],check=False);launcher=p.setdefault('launcher',{})
            launcher['playtime_seconds']=int(launcher.get('playtime_seconds',0))+seconds;self.store.save(p)
        except Exception:pass  # Play time must never block stopping a game.
    def mod_state(self, game):
        # Play already validates original/prepared APK hashes. A timer-picker
        # refresh needs metadata only, not synchronous hashing on the UI thread.
        p = self.store.load(game, check=False)
        if not getattr(find(p), 'mods', False):
            raise RevivalError('Mods are only available for games whose plugin provides them.')
        if not self.active or self.active['game'] != game:
            raise RevivalError('Press Play on this game before using Mods.')
        state = getattr(getattr(getattr(self.android, 'backend', None), 'server', None), 'state', None)
        if state is None:
            raise RevivalError('The local game service is unavailable. Stop the game and press Play again.')
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
            process_gone=not pid
            if pid and self.game_left_screen():
                # Android keeps closed apps cached, so a live process is not proof
                # the game is open. End only after the game stays off screen for
                # several checks; a brief dialog from another app is tolerated.
                self.offscreen_checks+=1
                if self.offscreen_checks<OFFSCREEN_LIMIT:return None
                pid=''
            elif pid:self.offscreen_checks=0
            if pid:
                self.connection_failures=0
                state=getattr(getattr(self.android.backend,'server',None),'state',None)
                notice=state.take_action_notice() if state and hasattr(state,'take_action_notice') else None
                return 'Game action: '+notice if notice else None
            message='The game has closed.'
            if process_gone and self.capture_crash(self.active['game'],self.android,'The game process ended while playing.'):
                message='The game closed unexpectedly. A crash log was saved: Game options > Crash logs.'
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
    def game_left_screen(self):
        """True when Android reports resumed activities and none is this game's.

        Unknown output or a failed query counts as on screen, so a game is
        never ended because of a status-format difference.
        """
        try:output=self.android.shell('dumpsys','activity','activities',timeout=6)
        except RevivalError:return False
        resumed=[line for line in output.splitlines() if 'ResumedActivity' in line and 'ActivityRecord{' in line]
        return bool(resumed) and not any(' '+self.android.package+'/' in line for line in resumed)
    def android_runtime(self,ctx):
        ctx.step('Starting the game runtime');serial=self.runtime_manager.ensure(progress=ctx.step)
        return self.runtime_factory(serial)
    def backup(self,game,ctx):
        p=self.store.load(game)
        if host_saves(p):
            ctx.step('Backing up progress');return Saves(self.store).backup(game)
        if self.active:raise RevivalError('Stop the running game before backing up its progress.')
        from .. import android_saves
        runtime=self.android_runtime(ctx);ctx.step('Copying game progress from Android')
        return android_saves.backup(runtime,p,self.store.directory(game)/'backups'/(now().replace(':','-')+'-'+uuid.uuid4().hex[:6]+'.zip'))
    def backups(self,game):
        folder=self.store.directory(game)/'backups'
        return sorted(folder.glob('*.zip'),key=lambda x:x.stat().st_mtime,reverse=True) if folder.is_dir() else []
    def game_actions(self,game):
        """Extra buttons a game's plugin offers in Game options."""
        plugin=find(self.store.load(game,check=False))
        return plugin.game_actions(self.store.load(game,check=False)) if hasattr(plugin,'game_actions') else []
    def run_game_action(self,game,key,ctx):
        plugin=find(self.store.load(game,check=False))
        if not hasattr(plugin,'run_action'):raise RevivalError('This game has no plugin actions.')
        return plugin.run_action(self,game,key,ctx)
    def restore(self,game,backup,ctx):
        from .. import android_saves
        p=self.store.load(game)
        if host_saves(p):
            self.stop();ctx.step('Preserving the current save and restoring backup');return Saves(self.store).restore(game,backup)
        if self.active:raise RevivalError('Stop the running game before restoring its progress.')
        android_saves.read_meta(backup)
        runtime=self.android_runtime(ctx)
        # Reversible: keep the current progress before replacing it.
        ctx.step('Backing up current progress first')
        try:prior=android_saves.backup(runtime,p,self.store.directory(game)/'backups'/(now().replace(':','-')+'-before-restore.zip'))
        except RevivalError as error:
            if 'No saved data' not in str(error):raise
            prior=None
        ctx.step('Restoring the selected backup');result=android_saves.restore(runtime,p,backup)
        result['previous_backup']=prior;return result
    def remove_game(self,game,uninstall,ctx):
        """Remove a library entry. Saves and backups are kept in removed-games/."""
        if self.active and self.active['game']==game:raise RevivalError('Stop this game before removing it.')
        p=self.store.load(game,check=False);uninstalled=False
        if uninstall:
            from .. import android_saves
            package=android_saves.package_for(p)
            runtime=self.android_runtime(ctx)
            if 'package:' in runtime.shell('pm','path',package,timeout=20):
                if not host_saves(p):
                    # Never uninstall without a successful backup of its progress.
                    ctx.step('Backing up progress before uninstalling')
                    try:android_saves.backup(runtime,p,self.store.directory(game)/'backups'/(now().replace(':','-')+'-before-uninstall.zip'))
                    except RevivalError as error:
                        if 'No saved data' not in str(error):raise RevivalError('The game was not removed: its progress could not be backed up first. '+str(error)) from error
                ctx.step('Uninstalling the game from Android');runtime.adb('uninstall',package,timeout=120);uninstalled=True
        ctx.step('Removing the game from your library');kept=self.store.remove(game)
        return {'removed':True,'title':p['title'],'uninstalled':uninstalled,'kept':kept}
    def add_to_steam(self,game,icon=None,artwork=None):
        if not getattr(sys,'frozen',False):raise RevivalError('Steam shortcuts for games are available in the packaged Linux app.')
        p=self.store.load(game,check=False)
        from .steam import register
        return register(pathlib.Path(sys.executable),name=p['title'],launch_options='--fullscreen --play '+game,icon=str(icon or ''),artwork=artwork)
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
        report={'schema_version':1,'version':__version__,'apk_sha256':p['apk_sha256'],'apk_version':p['apk_version'],'status':p['status'],'analysis':p['analysis'],'restoration_path':p['restoration']['path'],'verification':p['verification'],'runtime':self.runtime_manager.last,'library_errors':self.store.last_library_errors,'job_history':[j.snapshot() for j in self.jobs.history[-20:]],'servers_contacted':[{k:r[k] for k in ('host','port','secure','count')} for r in server_summary(self.network_log(game))[:100]]}
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

