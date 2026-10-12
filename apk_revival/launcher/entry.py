"""Packaged launcher entry, including a desktop install flow."""
import argparse,fcntl,os,pathlib,sys,signal

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fullscreen',action='store_true');parser.add_argument('--data');parser.add_argument('--install',action='store_true');parser.add_argument('--smoke',action='store_true');parser.add_argument('--update-probe',action='store_true');parser.add_argument('--apply-update',help=argparse.SUPPRESS);parser.add_argument('--wait-pid',type=int,help=argparse.SUPPRESS);parser.add_argument('--smoke-service',help=argparse.SUPPRESS);args=parser.parse_args()
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
    if args.smoke_service:
        from ..meego.backend import MeegoBackend,config_path
        import json,urllib.request
        profile=store.load(args.smoke_service)
        if profile.get('adapter')!='meego-1.32':raise ValueError('Service smoke check requires prepared Meego data')
        backend=MeegoBackend(store.directory(profile['id']),config_path(store,profile),0).start()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{backend.port}/health',timeout=5) as response:value=json.load(response)
            if value['token']!=backend.token:raise ValueError('Service health identity mismatch')
            print('PASS: packaged Meego host service startup and health. Android unverified.')
        finally:backend.stop()
        return 0
    lock=open(store.root/'launcher.lock','a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        from PySide6.QtWidgets import QApplication,QMessageBox
        app=QApplication.instance() or QApplication(sys.argv);QMessageBox.information(None,'APK Revival','APK Revival is already running. Return to its window.');return 1
    from .ui import Window
    from .style import STYLE
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app=QApplication(sys.argv);app.setApplicationName('APK Revival');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    if (pathlib.Path(sys.executable).parent/'bundle.json').exists() and getattr(sys,'frozen',False):
        from .portable import PortableWindow
        window=PortableWindow(pathlib.Path(sys.executable).parent)
    else:window=Window(store,args.fullscreen)
    signal.signal(signal.SIGTERM,lambda *_:QTimer.singleShot(0,window.close))
    signal.signal(signal.SIGINT,lambda *_:QTimer.singleShot(0,window.close))
    window.show()
    if args.smoke:QTimer.singleShot(1800,window.close);QTimer.singleShot(5000,app.quit)
    return app.exec()

