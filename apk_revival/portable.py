from __future__ import annotations
import argparse, pathlib, time
from .runtime import WaydroidRuntime
from .backend import Backend
from .util import RevivalError, digest, read_json, safe_member


def main():
    parser=argparse.ArgumentParser(description='Run an APK Revival export, preserving fixture boundaries')
    parser.add_argument('--serial');args=parser.parse_args();root=pathlib.Path(__file__).resolve().parents[1]
    try:
        # Corruption detection only, not an authenticity signature. Do not trust unknown bundles.
        for filename,sha in read_json(root/'hashes.json').items():
            safe_member(filename)
            if digest(root/filename)!=sha:raise RevivalError('Bundle integrity check failed: '+filename)
        b=read_json(root/'bundle.json');p=read_json(root/'profile.json')
        if b['path']=='rebuild':
            from .rebuild_game import run
            run(root/'saves/rebuild.json');return
        r=WaydroidRuntime(args.serial);r.compatible(p);r.package=p['restoration'].get('client_package',p['analysis']['metadata']['package'])
        try:
            r.adb('install','-r',root/'restored.apk',timeout=180)
            for i in b['supporting']:
                if i['role']=='obb':
                    dest='/sdcard/Android/obb/'+r.package;r.shell('mkdir','-p',dest);r.adb('push',root/i['file'],dest+'/'+i['name'],timeout=180)
            if b['path']=='local_backend':
                port=b['backend_port']
                if p['adapter']=='tapquest-v1':r.backend=Backend(root/'saves/tapquest.json',port).start()
                else:
                    from .adapters import adapter,load_plugins
                    load_plugins(root/'plugins')
                    plugin=adapter(p)
                    if not hasattr(plugin,'start_backend'):raise RevivalError('Unsupported backend adapter')
                    r.backend=plugin.start_backend(root/'portable-data',root/'backend-data',port,apk=root/'restored.apk')
                r.adb('reverse','--no-rebind',f'tcp:{port}',f'tcp:{port}');r.forward_port=port;r.probe_backend()
            r.launch(p);print('Game started. Keep this window open. Ctrl+C stops it.')
            while True:time.sleep(.5)
        except KeyboardInterrupt:pass
        finally:r.stop()
    except RevivalError as e:parser.exit(1,str(e)+'\n')

