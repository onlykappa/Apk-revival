"""User-local desktop installation. No system package manager or sudo."""
from __future__ import annotations
import os,pathlib,shutil,sys
from ..util import RevivalError

def desktop_escape(value):return str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')

def install(source=None,home=None):
    source=pathlib.Path(source or pathlib.Path(sys.executable).resolve().parent)
    if not (source/'APK-Revival').is_file():raise RevivalError('The update executable is missing; installed application was not changed')
    home=pathlib.Path(home or pathlib.Path.home());target=home/'.local/share/apk-revival-app'
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.resolve()!=target.resolve():
        staged=target.with_name('apk-revival-app.new');prior=target.with_name('apk-revival-app.previous')
        if staged.exists():shutil.rmtree(staged)
        shutil.copytree(source,staged)
        if prior.exists():shutil.rmtree(prior)
        if target.exists():target.rename(prior)
        try:staged.rename(target)
        except Exception:
            if prior.exists() and not target.exists():prior.rename(target)
            raise
    exe=target/'APK-Revival'
    if not exe.is_file():raise RevivalError('The packaged APK-Revival executable is missing')
    exe.chmod(exe.stat().st_mode|0o111)
    icon=target/'_internal/resources/apk-revival-logo.png'
    if not icon.exists():icon=target/'_internal/resources/apk-revival.svg'
    applications=home/'.local/share/applications';applications.mkdir(parents=True,exist_ok=True)
    desktop='[Desktop Entry]\nType=Application\nName=APK Revival\nComment=Your mobile games, back in play\nExec="'+desktop_escape(exe)+'" --fullscreen\nIcon='+str(icon)+'\nTerminal=false\nCategories=Game;\nStartupNotify=true\n'
    path=applications/'apk-revival.desktop';path.write_text(desktop);path.chmod(0o755)
    desktop_dir=home/'Desktop'
    if desktop_dir.is_dir():shutil.copyfile(path,desktop_dir/'APK Revival.desktop');(desktop_dir/'APK Revival.desktop').chmod(0o755)
    return {'executable':str(exe),'desktop_file':str(path),'previous_install':str(target.with_name('apk-revival-app.previous'))}

def install_dialog():
    from PySide6.QtWidgets import QApplication,QMessageBox
    app=QApplication.instance() or QApplication(sys.argv)
    if QMessageBox.question(None,'Install APK Revival','Install APK Revival in your home folder and create an application-menu shortcut? No administrator password is needed. A previous installation is preserved.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return 0
    try:
        result=install();QMessageBox.information(None,'APK Revival installed','Open APK Revival from your application menu.\n\nFor Steam: choose Games > Add a Non-Steam Game, select APK Revival, and add --fullscreen to its launch options.');return 0
    except Exception as e:QMessageBox.critical(None,'Installation failed',str(e));return 1

