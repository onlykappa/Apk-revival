from __future__ import annotations
import time, uuid
from .runtime import OfflineGuard, WaydroidRuntime
from .util import RevivalError, atomic_json, digest, now

CHECKS=['cold_launch','meaningful_gameplay','representative_action','save_progress','close_and_relaunch','load_saved_progress','backend_failure_recovery']

def passes(record):
    return record.get('kind')=='android_gameplay' and record.get('external_network_blocked') is True and all(record.get('checks',{}).get(k) is True for k in CHECKS)

def verify(store,game_id):
    p=store.load(game_id)
    if p.get('adapter')!='tapquest-v1':raise RevivalError('Needs Evidence: generic runtime diagnostics are available; automated gameplay verification requires a game-specific verifier.')
    if p['restoration']['path']=='rebuild':raise RevivalError('Rebuild verification is separate. APK cannot be marked Verified Offline by testing a rebuild.')
    r=WaydroidRuntime(p['runtime']['serial']);d=store.directory(game_id)/'verification-artifacts'/uuid.uuid4().hex;d.mkdir(parents=True)
    record={'kind':'android_gameplay','fixture':True,'time':now(),'artifact_sha256':p['restoration'].get('artifact_sha256'),'external_network_blocked':False,'checks':{k:False for k in CHECKS},'unverified':['No commercial APK restored','No device reboot, long-session or exhaustive mechanics coverage']}
    try:
        r.install(store,p);r.shell('am','force-stop',r.package)
        with OfflineGuard(r) as guard:
            record['external_network_blocked']=True;record['firewall']=guard.evidence
            r.adb('logcat','-c')
            if p['restoration']['path']=='local_backend':r.start_backend(store,p)
            r.launch(p);initial=r.fixture_event('ready');record['checks']['cold_launch']=True;record['checks']['meaningful_gameplay']=True
            r.adb('logcat','-c');r.tap_text('Collect coin');action=r.fixture_event('saved')
            if action['coins']!=initial['coins']+1:raise RevivalError('Representative action did not increment progress')
            record['checks']['representative_action']=True;record['checks']['save_progress']=True
            r.shell('am','force-stop',r.package);r.adb('logcat','-c');r.launch(p);loaded=r.fixture_event('ready')
            record['checks']['close_and_relaunch']=True
            if loaded['coins']!=action['coins']:raise RevivalError('Saved progress was not loaded')
            record['checks']['load_saved_progress']=True
            if r.backend:
                # Actual failure, then fresh backend start, guest probe and user retry.
                r.stop_backend();r.shell('am','force-stop',r.package);r.adb('logcat','-c');r.launch(p);r.fixture_event('backend_error')
                r.start_backend(store,p);r.adb('logcat','-c');r.tap_text('Retry');recovered=r.fixture_event('ready')
                if recovered['coins']!=action['coins']:raise RevivalError('Backend recovery lost progression')
                record['checks']['backend_failure_recovery']=True
            else:record['checks']['backend_failure_recovery']=True;record['backend_failure_recovery_note']='Not applicable: offline patch has no backend'
            record['observations']={'initial':initial,'action':action,'reloaded':loaded}
            (d/'logcat.txt').write_text(r.adb('logcat','-d','-v','threadtime'))
            # Re-check artifact on disk; verification belongs to these exact bytes.
            if digest(r.artifact(store,p))!=record['artifact_sha256']:raise RevivalError('Artifact changed during verification')
        record['passed']=passes(record)
    except Exception as e:
        record['passed']=False;record['error']=str(e)
    finally:
        try:r.stop()
        except Exception as e:record['passed']=False;record['cleanup_error']=str(e)
        record['evidence_directory']=str(d.relative_to(store.directory(game_id)))
        atomic_json(d/'result.json',record);p['verification'].append(record)
        p['status']='Verified Offline' if record['passed'] else 'Exported but Unverified' if p['restoration'].get('export') else 'Restoration In Progress';store.save(p)
    return record

