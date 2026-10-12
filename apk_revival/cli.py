from __future__ import annotations
import argparse, json, sys, time
from .store import Store
from .util import RevivalError, atomic_json


def main(argv=None):
    parser=argparse.ArgumentParser(description='APK Revival local restoration workbench')
    parser.add_argument('--data',help='Private local data root (default ~/.local/share/apk-revival)')
    sub=parser.add_subparsers(dest='command')
    sub.add_parser('gui');sub.add_parser('legacy-gui');sub.add_parser('list')
    x=sub.add_parser('launcher');x.add_argument('--fullscreen',action='store_true')
    x=sub.add_parser('doctor');x.add_argument('--serial')
    x=sub.add_parser('import');x.add_argument('apk');x.add_argument('--support',nargs='*',default=[])
    for role in ['assets','logs','saves']:x.add_argument('--'+role,nargs='*',default=[])
    x=sub.add_parser('attach');x.add_argument('game');x.add_argument('files',nargs='*')
    for role in ['assets','logs','saves']:x.add_argument('--'+role,nargs='*',default=[])
    for c in ['analyze','report','reset','verify']:
        x=sub.add_parser(c);x.add_argument('game')
    for c in ['plan','prepare']:
        x=sub.add_parser(c);x.add_argument('game');x.add_argument('path',choices=['offline_patch','local_backend','rebuild'])
        if c=='prepare':x.add_argument('--plan',help='Reviewed local plan JSON, exact hash/version required')
    x=sub.add_parser('runtime');x.add_argument('game');x.add_argument('--serial',required=True);x.add_argument('--backend-port',type=int,default=18765)
    x=sub.add_parser('play');x.add_argument('game')
    x=sub.add_parser('stop');x.add_argument('game')
    x=sub.add_parser('diagnostics');x.add_argument('game');x.add_argument('--original',action='store_true')
    x=sub.add_parser('export');x.add_argument('game');x.add_argument('output')
    x=sub.add_parser('backup');x.add_argument('game');x.add_argument('--output')
    x=sub.add_parser('restore');x.add_argument('game');x.add_argument('backup')
    args=parser.parse_args(argv);s=Store(args.data)
    try:
        c=args.command or 'gui';result=None
        if c in ['gui','launcher']:
            try:from .launcher.ui import run
            except ImportError:raise RevivalError('V2 requires PySide6. Use the packaged Linux download, or install the launcher extra. V1 remains available through legacy-gui and the CLI.')
            return run(s,getattr(args,'fullscreen',False))
        if c=='legacy-gui':
            from .ui import run
            run(s);return
        if c=='list':result=[{'id':p['id'],'title':p['title'],'status':p['status'],'fixture':bool(p['analysis'] and p['analysis']['fixture'])} for p in s.games()]
        elif c=='doctor':
            from .runtime import WaydroidRuntime
            result=WaydroidRuntime(args.serial).probe()
        elif c=='import':result=s.import_game(args.apk,args.support+[(role,v) for option,role in [('assets','asset'),('logs','log'),('saves','save')] for v in getattr(args,option)])
        elif c=='attach':result=s.attach(args.game,args.files+[(role,v) for option,role in [('assets','asset'),('logs','log'),('saves','save')] for v in getattr(args,option)])
        elif c=='analyze':
            from .analysis import analyze
            result=analyze(s,args.game)
        elif c=='report':
            from .analysis import markdown
            p=s.load(args.game)
            if not p['analysis']:raise RevivalError('Analyze first')
            print(markdown(p));return
        elif c=='reset':result=s.reset(args.game)
        elif c in ['plan','prepare']:
            from .restoration import Restorer
            result=Restorer(s).plan(args.game,args.path) if c=='plan' else Restorer(s).prepare(args.game,args.path,args.plan)
        elif c=='runtime':
            if not 1024<=args.backend_port<=65535:raise RevivalError('Use backend port 1024..65535')
            p=s.load(args.game)
            changed=p['runtime']['backend_port']!=args.backend_port
            p['runtime'].update(serial=args.serial,backend_port=args.backend_port)
            if changed and p['restoration']['path']=='local_backend':p['restoration']={'path':None,'operations':[],'artifact':None};p['status']='Analyzed';p['verification']=[]
            s.save(p);result=p['runtime']
        elif c=='play':
            p=s.load(args.game)
            if p['restoration']['path']=='rebuild':
                from .rebuild_game import run
                if not p['rebuild']['feasibility']:raise RevivalError('Prepare rebuild first')
                run(s.directory(args.game)/'saves/rebuild.json');return
            from .runtime import WaydroidRuntime
            r=WaydroidRuntime(p['runtime']['serial'])
            try:
                print(json.dumps(r.start(s,p)));print('Ctrl+C stops game, backend and forwarding.')
                while True:time.sleep(.5)
            except KeyboardInterrupt:pass
            finally:r.stop()
            return
        elif c=='stop':
            from .runtime import WaydroidRuntime
            p=s.load(args.game);r=WaydroidRuntime(p['runtime']['serial']);r.package=p['analysis']['metadata']['package'];r.stop();result={'stopped':True,'note':'A running play launcher owns its backend. Ctrl+C that launcher to release the backend port.'}
        elif c=='diagnostics':
            from .runtime import WaydroidRuntime
            p=s.load(args.game);r=WaydroidRuntime(p['runtime']['serial'])
            try:result=r.diagnostics(s,p,args.original)
            finally:r.stop()
        elif c=='verify':
            from .verification import verify
            result=verify(s,args.game)
            print(json.dumps(result,indent=2));return 0 if result['passed'] else 2
        elif c=='export':
            from .exporter import export_game
            result=export_game(s,args.game,args.output)
        elif c in ['backup','restore']:
            from .saves import Saves
            result=Saves(s).backup(args.game,args.output) if c=='backup' else Saves(s).restore(args.game,args.backup)
        print(json.dumps(result,indent=2))
    except (RevivalError,OSError,ValueError,KeyError) as e:
        print('APK Revival: '+str(e),file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
