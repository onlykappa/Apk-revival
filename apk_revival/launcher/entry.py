"""Packaged launcher entry, including a desktop install flow."""
import argparse,fcntl,os,pathlib,sys,signal

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test-pattern',default='test*.py',help=argparse.SUPPRESS);parser.add_argument('--test-suite',help=argparse.SUPPRESS);parser.add_argument('--launch-check',help=argparse.SUPPRESS);parser.add_argument('apks',nargs='*');parser.add_argument('--fullscreen',action='store_true');parser.add_argument('--data');parser.add_argument('--install',action='store_true');parser.add_argument('--smoke',action='store_true');parser.add_argument('--update-probe',action='store_true');parser.add_argument('--apply-update',help=argparse.SUPPRESS);parser.add_argument('--wait-pid',type=int,help=argparse.SUPPRESS);parser.add_argument('--smoke-service',help=argparse.SUPPRESS)
    controls=parser.add_mutually_exclusive_group()
    controls.add_argument('--play',metavar='GAME_ID',help='Play a saved library entry in the normal launcher')
    controls.add_argument('--stop-game',action='store_true',help='Stop the launcher-owned game')
    controls.add_argument('--restart-runtime',action='store_true',help='Restart the managed runtime after stopping the game')
    controls.add_argument('--quit',action='store_true',help='Close the normal launcher through its cleanup workflow')
    args=parser.parse_args()
    if args.test_suite:
        stdlib=os.environ.get('APKR_TEST_STDLIB')
        if stdlib:sys.path.extend([stdlib,str(pathlib.Path(stdlib)/'lib-dynload')])
        import unittest
        suite=unittest.defaultTestLoader.discover(args.test_suite,pattern=args.test_pattern)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if args.update_probe:
        import json
        from .. import __version__
        from .network import tls_context
        print(json.dumps({'version':__version__,'certificates':bool(tls_context().get_ca_certs())}))
        return 0
    if args.apply_update:
        from .updater import apply_update
        try:
            if not args.wait_pid or args.wait_pid<=1:raise ValueError('Missing update process identity')
            return apply_update(args.apply_update,args.wait_pid,args.fullscreen,args.data)
        except Exception as error:
            log=pathlib.Path.home()/'.cache/apk-revival/updates/last-error.txt'
            log.parent.mkdir(parents=True,exist_ok=True);log.write_text(str(error))
            from PySide6.QtWidgets import QApplication,QMessageBox
            app=QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None,'Update failed',str(error)+'\nYour games and saves were not changed. Reopen APK Revival.')
            return 1
    if args.install:
        from .install import install_dialog
        return install_dialog()
    from ..store import Store
    store=Store(args.data)
    action='play' if args.play else 'stop' if args.stop_game else 'restart-runtime' if args.restart_runtime else 'quit' if args.quit else None
    if action:
        if args.apks:parser.error('Open APKs and library controls must be separate requests.')
        from .requests import enqueue
        import json
        queued=enqueue(store,action,args.play)
        print(json.dumps(queued),flush=True)
    if args.launch_check:
        from .service import Launcher
        from ..util import RevivalError
        launcher=Launcher(store)
        try:
            launcher.jobs.run('Launch check',lambda ctx:launcher.play(args.launch_check,ctx),lambda update:print(update['steps'][-1]['label'] if update['steps'] else update['state'],flush=True))
            print('PASS: Android activity launched. Gameplay and retained data require observation.')
            return 0
        except Exception as error:
            print('FAIL: '+str(error),file=sys.stderr);return 1
        finally:launcher.shutdown()
    if args.smoke_service:
        from ..meego.backend import MeegoBackend,config_path
        import json,urllib.request
        profile=store.load(args.smoke_service)
        if profile.get('adapter')!='meego-1.32':raise ValueError('Service smoke check requires prepared Meego data')
        backend=MeegoBackend(store.directory(profile['id']),config_path(store,profile),0,apk=store.base(profile)).start()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{backend.port}/health',timeout=5) as response:value=json.load(response)
            if value['token']!=backend.token:raise ValueError('Service health identity mismatch')
            print('PASS: packaged Meego host service startup and health. Android unverified.')
        finally:backend.stop()
        return 0
    lock=open(store.root/'launcher.lock','a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        from ..util import atomic_json
        import uuid
        for apk in args.apks:
            path=pathlib.Path(apk).expanduser().resolve()
            atomic_json(store.root/'open-requests'/(uuid.uuid4().hex+'.json'),{'apk':str(path)})
        return 0
    from .ui import Window
    from .style import STYLE
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app=QApplication(sys.argv);app.setApplicationName('APK Revival');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    if (pathlib.Path(sys.executable).parent/'bundle.json').exists() and getattr(sys,'frozen',False):
        from .portable import PortableWindow
        window=PortableWindow(pathlib.Path(sys.executable).parent)
    else:window=Window(store,args.fullscreen,close_after_game=bool(args.play))
    signal.signal(signal.SIGTERM,lambda *_:QTimer.singleShot(0,window.close))
    signal.signal(signal.SIGINT,lambda *_:QTimer.singleShot(0,window.close))
    window.show()
    from .requests import process_requests
    def open_requests():process_requests(window)
    window.request_timer=QTimer(window);window.request_timer.timeout.connect(open_requests);window.request_timer.start(500)
    for apk in args.apks:QTimer.singleShot(0,lambda path=apk:window.open_apk(path))
    if args.smoke:
        screenshot=os.environ.get('APKR_SMOKE_SCREENSHOT')
        if screenshot:QTimer.singleShot(1400,lambda:window.grab().save(screenshot))
        QTimer.singleShot(1800,window.close);QTimer.singleShot(5000,app.quit)
    return app.exec()


