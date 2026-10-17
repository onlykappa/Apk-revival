from __future__ import annotations
import json, pathlib, shutil, tempfile, zipfile
from .runtime import WaydroidRuntime
from .util import RevivalError, atomic_json, digest
from .verification import passes


def export_game(store,game_id,output):
    p=store.load(game_id);path=p['restoration']['path'];output=pathlib.Path(output).resolve()
    if output.suffix.lower()!='.zip':raise RevivalError('Export output must be a ZIP file')
    if any(part in {'originals','signing'} for part in output.parts) and store.root in output.parents:raise RevivalError('Export cannot overwrite original inputs or signing storage')
    if path not in {'offline_patch','local_backend','rebuild'}:raise RevivalError('Prepare a supported restoration before export')
    if path=='rebuild' and not p['rebuild']['feasibility']:raise RevivalError('Rebuild feasibility missing')
    if path!='rebuild':artifact=WaydroidRuntime().artifact(store,p)
    with tempfile.TemporaryDirectory() as temp:
        root=pathlib.Path(temp);package=root/'apk_revival'
        shutil.copytree(pathlib.Path(__file__).parent,package,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        profile=json.loads(json.dumps(p));profile['runtime']['serial']=None;profile['logs']=[];profile['restoration'].pop('export',None)
        if path!='rebuild':
            shutil.copyfile(artifact,root/'restored.apk');profile['restoration']['artifact']='restored.apk'
            d=store.directory(game_id);diff=d/p['restoration']['diff'];shutil.copyfile(diff,root/'changes.diff')
            sign=artifact.parent/'signature-verification.txt';shutil.copyfile(sign,root/'signature-verification.txt')
        if path=='rebuild':
            profile['verification']=[];profile['status']='Exported but Unverified'
            profile['rebuild']['status']='Independent fixture implementation; Android restoration not claimed'
        else:
            verified=any(x.get('passed') and passes(x) and x.get('artifact_sha256')==digest(artifact) for x in p['verification'])
            profile['status']='Verified Offline' if verified else 'Exported but Unverified'
        supporting=[]
        if path!='rebuild':
            for i in p['inputs']:
                if i['role'] not in {'obb','asset'}:continue
                rel=i.get('relative_path',i['name']);from .util import safe_member
                safe_member(rel);dest=root/'support'/rel
                if dest.exists():raise RevivalError('Supporting asset destination collision: '+rel)
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(store.directory(game_id)/'originals'/i['stored_name'],dest)
                supporting.append({'role':i['role'],'file':'support/'+rel,'name':i['name']})
        from .adapters import find
        plugin=find(p)
        if plugin is not None and hasattr(plugin,'config_path') and path=='local_backend':
            config=plugin.config_path(store,p);shutil.copytree(config,root/'backend-data');profile['restoration']['backend_data']['directory']='backend-data'
            # Portable copies need the game's plugin, since the app download leaves plugins out.
            from .plugins import source_for
            source=source_for(p.get('adapter'))
            if source:shutil.copytree(source,root/'plugins'/pathlib.Path(source).name)
        atomic_json(root/'profile.json',profile)
        if p['analysis']:
            from .analysis import markdown
            (root/'analysis.md').write_text(markdown(profile))
        atomic_json(root/'bundle.json',{'schema_version':1,'path':path,'profile':'profile.json','supporting':supporting,'fixture':p['analysis']['fixture'],'backend_port':p['runtime']['backend_port']})
        (root/'run.py').write_text('from apk_revival.portable import main\nif __name__ == "__main__": main()\n')
        (root/'README.md').write_text(f'''# APK Revival portable export\n\nPath: {path}. Status: {profile['status']}.\n\nUnzip into a writable folder. Python 3.10+ is required.\n\nFor Android: initialize Waydroid separately, connect ADB, then:\n\n    python3 run.py --serial GUEST_IP:5555\n\nFor a separate rebuild:\n\n    python3 run.py\n\nKeep this launcher running while using a local backend. Ctrl+C stops the app, forwarding and backend.\n\nOnly loopback local communication is used by the fixture backend. The launcher tests Android-to-host reachability using a fresh health token before launch. Guest toybox nc is required. This launcher does not enforce external network blocking; use the main workbench Verify workflow for that.\n\nOBBs are installed under /sdcard/Android/obb/PACKAGE/. Other supporting assets require game-specific placement instructions; unknown placement is not invented.\n\nNo original APK, private saves, logs or signing key is included. Saves created during play remain in this folder. Re-signed APKs may conflict with an installed original signature. Back up that original's data before independently choosing to remove it. The launcher never silently uninstalls it.\n\n{'Self-authored fixture, not restoration of a real game.' if p['analysis']['fixture'] else 'Game restoration claims are limited to profile verification evidence.'}\n''')
        hashes={str(f.relative_to(root)):digest(f) for f in sorted(root.rglob('*')) if f.is_file()}
        atomic_json(root/'hashes.json',hashes)
        output.parent.mkdir(parents=True,exist_ok=True)
        # Write a temporary ZIP then atomically replace only after completion.
        staged=output.with_suffix(output.suffix+'.tmp')
        try:
            with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED) as z:
                for f in sorted(root.rglob('*')):
                    if f.is_file():z.write(f,str(f.relative_to(root)))
            staged.replace(output)
        finally:
            if staged.exists():staged.unlink()
    p['restoration']['export']={'path':str(output),'sha256':digest(output)}
    if p['status']!='Verified Offline':p['status']='Exported but Unverified'
    store.save(p);return {'file':str(output),'sha256':digest(output),'status':p['status'],'path':path}

