"""Packaged launcher entry, including a desktop install flow."""
import argparse,fcntl,os,pathlib,sys

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fullscreen',action='store_true');parser.add_argument('--data');parser.add_argument('--install',action='store_true');parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    if args.install:
        from .install import install_dialog
        return install_dialog()
    from ..store import Store
    store=Store(args.data);lock=open(store.root/'launcher.lock','a+')
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
    window.show()
    if args.smoke:QTimer.singleShot(1800,window.close);QTimer.singleShot(5000,app.quit)
    return app.exec()
