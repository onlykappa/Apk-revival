"""Guided real-Android verification with user observations and host evidence.

Native OpenGL UI has no reliable text automation. Confirmations are explicit
human observations, never fabricated by static inspection or HTTP tests.
"""
import copy,json,pathlib,uuid
from ..runtime import OfflineGuard
from ..util import RevivalError,atomic_json,digest,now
from ..verification import CHECKS,passes

class GuidedTest:
    def __init__(self,store,game,runtime_factory=None):
        from ..launcher.runtime_setup import ManagedAndroid
        self.store=store;self.game=game;self.p=store.load(game);self.factory=runtime_factory or ManagedAndroid;self.r=None;self.guard=None;self.stage='new';self.finished=False
        self.directory=store.directory(game)/'verification-artifacts'/uuid.uuid4().hex;self.directory.mkdir(parents=True)
        self.record={'kind':'android_gameplay','fixture':False,'verification_mode':'guided_user_observations_and_runtime_evidence','time':now(),'artifact_sha256':self.p['restoration'].get('artifact_sha256'),'external_network_blocked':False,'checks':{k:False for k in CHECKS},'user_observations':[],'remaining_unverified':['Unexercised quests, social features, visual equipment effects, breeding and full original balance']}
    def start(self,serial):
        if self.stage!='new':raise RevivalError('Verification has already started')
        self.r=self.factory(serial);self.r.install(self.store,self.p);self.r.start_backend(self.store,self.p)
        self.guard=OfflineGuard(self.r);self.record['runtime_serial']=serial;self.record['owned_network_chain']=self.guard.chain
        atomic_json(self.directory/'in-progress.json',self.record)
        try:
            self.guard.__enter__();self.record['external_network_blocked']=True;self.record['network_guard']=self.guard.evidence;atomic_json(self.directory/'in-progress.json',self.record)
            self.logfile=self.r.backend.server.state.logfile;self.offset=self.logfile.stat().st_size if self.logfile.exists() else 0
            self.r.launch(self.p);self.stage='village';return 'Is the village visible? Pan or zoom and open a menu, then confirm.'
        except Exception:self.finish(False,'Could not establish the Android offline test');raise
    def snapshot(self):
        state=self.r.backend.server.state
        with state.lock:return copy.deepcopy(state.data)
    def confirm_village(self):
        self.require('village');self.record['checks'].update(cold_launch=True,meaningful_gameplay=True);self.record['user_observations'].append('Village rendered, pan/zoom or menu interaction observed');self.stage='action';return 'Buy/place or upgrade one building in Meego. After it appears, confirm the action.'
    def confirm_action(self):
        self.require('action');events=[]
        if self.logfile.exists():
            with self.logfile.open('rb') as stream:stream.seek(self.offset);lines=stream.read(1024*1024).decode(errors='replace').splitlines()
            for line in lines:
                try:
                    event=json.loads(line)
                    if event.get('status')=='saved-local-action' and event.get('route','').strip('/') in {'game/village/place_building','game/village/upgrade_building','game/village/change_building'}:events.append({'route':event['route'],'time':event['time'],'status':event['status']})
                except (ValueError,KeyError):pass
        if not events:raise RevivalError('No successful building purchase/upgrade request was observed during this test. Complete that action in the game, then retry confirmation.')
        self.record['action_evidence']=events;self.record['checks'].update(representative_action=True,save_progress=True)
        self.r.shell('am','force-stop',self.r.package);saved=self.snapshot();self.r.stop_backend();self.r.start_backend(self.store,self.p)
        if self.snapshot()!=saved:raise RevivalError('Saved village changed during backend restart')
        self.r.launch(self.p);self.record['checks']['close_and_relaunch']=True;self.stage='loaded';return 'The game and local service were restarted. Confirm that the purchased/upgraded building is still present.'
    def confirm_loaded(self):
        self.require('loaded');self.record['checks']['load_saved_progress']=True;self.record['user_observations'].append('Building change visible after game and backend restart');self.r.stop_backend();self.r.shell('am','force-stop',self.r.package);
        from ..runtime import WaydroidRuntime
        WaydroidRuntime.launch(self.r,self.p);self.stage='failure';return 'The local service is intentionally stopped. Confirm that Meego cannot load its village or reports a connection error.'
    def confirm_failure(self):
        self.require('failure');self.record['user_observations'].append('Connection failure visible with local backend stopped');self.r.shell('am','force-stop',self.r.package);self.r.start_backend(self.store,self.p);self.r.launch(self.p);self.stage='recovered';return 'The service has restarted and Android reachability passed. Confirm the village loads and your building change is still present.'
    def confirm_recovered(self):
        self.require('recovered');self.record['checks']['backend_failure_recovery']=True;self.record['user_observations'].append('Village and saved building change visible after service failure/recovery');self.stage='done';return self.finish(True)
    def require(self,stage):
        if self.finished or self.stage!=stage:raise RevivalError('Verification steps must be completed in order')
    def finish(self,success=False,error=None):
        if self.finished:return self.record
        self.finished=True
        if error:self.record['error']=error
        try:
            if self.r:
                try:(self.directory/'logcat.txt').write_text(self.r.adb('logcat','-d','-v','threadtime',timeout=20))
                except RevivalError:pass
                try:self.r.stop()
                finally:
                    if self.guard:self.guard.__exit__(None,None,None)
                if digest(self.r.artifact(self.store,self.p))!=self.record['artifact_sha256']:raise RevivalError('Artifact changed during verification')
        except Exception as e:self.record['cleanup_error']=str(e);success=False
        self.record['passed']=bool(success and passes(self.record));self.record['evidence_directory']=str(self.directory.relative_to(self.store.directory(self.game)));atomic_json(self.directory/'result.json',self.record)
        p=self.store.load(self.game);p['verification'].append(self.record);
        if (self.directory/'in-progress.json').exists():(self.directory/'in-progress.json').unlink()
        p['status']='Verified Offline' if self.record['passed'] else 'Exported but Unverified' if p['restoration'].get('export') else 'Restoration In Progress';self.store.save(p);return self.record
