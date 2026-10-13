"""User readiness is separate from V1's evidence/verification status."""
from ..verification import passes

def readiness(p,runtime_ready=False):
    a=p.get('analysis');rest=p.get('restoration',{})
    if not a:return {'label':'Imported','detail':'Checking this game before preparation.','prepare':False,'play':False}
    if a.get('input_errors'):return {'label':'Additional files needed','detail':'The supplied split files do not match this APK version. Add the matching files.','prepare':False,'play':False}
    if not p.get('adapter'):return {'label':'Restoration work needed','detail':'This game needs a game-specific adapter. Export diagnostics to investigate its server dependencies.','prepare':False,'play':False}
    # The chosen path can change in Advanced settings without overwriting the
    # existing prepared artifact. It takes effect only after Prepare is selected.
    preferred=p.get('launcher',{}).get('preferred_path')
    if preferred and preferred!=rest.get('path'):
        return {'label':'Ready to prepare','detail':'The preparation method changed. Prepare this version once, then Play.','prepare':True,'play':False}
    if rest.get('path')=='rebuild' and p.get('rebuild',{}).get('feasibility'):
        return {'label':'Separate rebuild ready','detail':'Ready to Play. This independent implementation does not verify the original APK.','prepare':False,'play':True}
    if rest.get('artifact'):
        verified=any(v.get('passed') and passes(v) and v.get('artifact_sha256')==rest.get('artifact_sha256') for v in p.get('verification',[]))
        tested=any(x.get('kind')=='android_activity' and x.get('artifact_sha256')==rest.get('artifact_sha256') for x in p.get('launcher',{}).get('launch_checks',[]))
        return {'label':'Verified Offline' if verified else 'Launch tested' if tested else 'Prepared', 'detail':'Offline gameplay checks passed. Play anytime.' if verified else 'Ready to Play. Android will connect at launch when available; offline gameplay has not yet been verified.', 'prepare':False,'play':True}
    return {'label':'Ready to prepare','detail':'A supported restoration path is available. Prepare creates a separate working copy.','prepare':True,'play':False}

CONTROL_PROFILES={
 'tapquest-v1':{'label':'Touch / mouse','description':'Original Android fixture: tap Collect coin with touch or the Steam Deck trackpad. Separate rebuild: A / Enter collects, B / Esc returns.','android':'touch','rebuild':'controller'}
}
