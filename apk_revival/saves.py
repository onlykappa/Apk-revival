"""Backups stay local and are never silently included in an export."""
from __future__ import annotations
import pathlib, re, shlex, uuid, zipfile
from .runtime import WaydroidRuntime
from .util import RevivalError, atomic_json, digest, inspect_zip, now, read_json

class Saves:
    def __init__(self,store):self.store=store
    def backup(self,game_id,output=None):
        p=self.store.load(game_id);d=self.store.directory(game_id)
        plugin=host_save_plugin(p)
        if p.get('adapter')!='tapquest-v1' and plugin is None:raise RevivalError('Save locations unknown. Add a game-specific adapter before backup/restore.')
        path=p['restoration']['path'];target=pathlib.Path(output) if output else d/'backups'/f'{uuid.uuid4().hex}.zip';target.parent.mkdir(parents=True,exist_ok=True)
        data=None
        if path in ['local_backend','rebuild']:
            source=d/(plugin.save_file if plugin else 'saves/tapquest.json' if path=='local_backend' else 'saves/rebuild.json')
            if not source.exists():raise RevivalError('No saved progress exists yet')
            data=source.read_bytes();filename='progress.json'
        elif path=='offline_patch':
            r=WaydroidRuntime(p['runtime']['serial']);package=p['analysis']['metadata']['package'];r.shell('am','force-stop',package)
            data=r.shell('run-as',package,'cat','shared_prefs/tapquest.xml').encode();filename='tapquest.xml'
        else:raise RevivalError('Select/prepare a restoration first')
        import hashlib,json
        manifest={'schema_version':1,'apk_sha256':p['apk_sha256'],'path':path,'time':now(),'file':filename,'sha256':hashlib.sha256(data).hexdigest()}
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(filename,data);z.writestr('backup.json',json.dumps(manifest,indent=2))
        return str(target)
    def restore(self,game_id,backup):
        p=self.store.load(game_id);inspect_zip(backup,max_total=16*1024**2)
        import hashlib,json
        with zipfile.ZipFile(backup) as z:
            meta=json.loads(z.read('backup.json'))
            if meta.get('schema_version')!=1 or meta['apk_sha256']!=p['apk_sha256'] or meta['path']!=p['restoration']['path']:raise RevivalError('Backup belongs to a different APK version or restoration path')
            name=meta['file']
            if name not in {'progress.json','tapquest.xml'}:raise RevivalError('Unsupported backup member')
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise RevivalError('Backup hash mismatch')
        path=p['restoration']['path'];d=self.store.directory(game_id)
        # Reversible restore: preserve the current state when available.
        try:prior=self.backup(game_id)
        except RevivalError:prior=None
        if path in ['local_backend','rebuild']:
            state=json.loads(data)
            plugin=host_save_plugin(p)
            if plugin:
                plugin.validate_save(state);atomic_json(d/plugin.save_file,state);return {'restored':True,'previous_backup':prior}
            if set(state)!={'coins','level'} or type(state['coins']) is not int or state['coins']<0 or state['level']!=1+state['coins']//10:raise RevivalError('Invalid save state')
            atomic_json(d/('saves/tapquest.json' if path=='local_backend' else 'saves/rebuild.json'),state)
        elif path=='offline_patch':
            import xml.etree.ElementTree as ET
            root=ET.fromstring(data)
            if root.tag!='map':raise RevivalError('Invalid SharedPreferences XML')
            r=WaydroidRuntime(p['runtime']['serial']);package=p['analysis']['metadata']['package'];r.shell('am','force-stop',package)
            # Only our debuggable fixture supports run-as. No blanket root data overwrite.
            r.adb('shell',f'run-as {shlex.quote(package)} sh -c '+shlex.quote('mkdir -p shared_prefs && cat > shared_prefs/tapquest.xml'),input=data.decode())
        else:raise RevivalError('Unsupported save restore')
        return {'restored':True,'previous_backup':prior}


def host_save_plugin(p):
    """The game plugin that keeps this game's progress in a host file, if any."""
    from .adapters import find
    plugin=find(p)
    return plugin if plugin is not None and getattr(plugin,'save_file',None) else None
