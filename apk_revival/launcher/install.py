"""User-local desktop installation. No system package manager or sudo."""
from __future__ import annotations
import os,pathlib,shutil,sys,shlex,time,re
from ..util import RevivalError

def desktop_escape(value):return str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')

def remove_old_copies(home=None,keep=1):
    """Delete all but the newest previous app copy, and update staging folders not in use."""
    home=pathlib.Path(home or pathlib.Path.home())
    try:
        running=pathlib.Path(sys.executable).resolve().parent
        previous=sorted(home.glob('.local/share/apk-revival-app.previous*'),key=lambda p:p.stat().st_mtime,reverse=True)
        for old in previous[keep:]:
            if old.resolve()!=running:shutil.rmtree(old,ignore_errors=True)
        for staged in home.glob('.cache/apk-revival/updates/staged-*'):
            if staged.resolve()!=running and running not in staged.resolve().parents:shutil.rmtree(staged,ignore_errors=True)
        for pattern in ('.local/share/applications/apk-revival.desktop.previous-*','.config/mimeapps.list.previous-*','.config/kde-mimeapps.list.previous-*'):
            for old in sorted(home.glob(pattern),key=lambda p:p.stat().st_mtime,reverse=True)[keep:]:old.unlink(missing_ok=True)
    except OSError:pass  # Clean-up must never stop the app from starting.

def install(source=None,home=None,register_steam=True):
    source=pathlib.Path(source or pathlib.Path(sys.executable).resolve().parent)
    if not (source/'APK-Revival').is_file():raise RevivalError('The update executable is missing; installed application was not changed')
    home=pathlib.Path(home or pathlib.Path.home());target=home/'.local/share/apk-revival-app'
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.resolve()!=target.resolve():
        staged=target.with_name('apk-revival-app.new');prior=target.with_name('apk-revival-app.previous')
        if staged.exists():shutil.rmtree(staged)
        shutil.copytree(source,staged)
        if prior.exists():
            prior=target.with_name('apk-revival-app.previous-'+str(time.time_ns()))
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
    # xdg-utils on SteamOS cannot resolve unnecessary quotes around a simple Exec path.
    launch=str(exe) if re.fullmatch(r'[A-Za-z0-9/_.-]+',str(exe)) else '"'+desktop_escape(exe)+'"'
    desktop='[Desktop Entry]\nType=Application\nName=APK Revival\nComment=Your mobile games, back in play\nExec='+launch+' --fullscreen %F\nMimeType=application/vnd.android.package-archive;\nIcon='+str(icon)+'\nTerminal=false\nCategories=Game;\nStartupNotify=true\n'
    path=applications/'apk-revival.desktop'
    if path.exists():shutil.copyfile(path,path.with_name(path.name+'.previous-'+str(time.time_ns())))
    path.write_text(desktop);path.chmod(0o755)
    bindir=home/'.local/bin';bindir.mkdir(parents=True,exist_ok=True)
    gaming=bindir/'apk-revival-gaming';gaming.write_text('#!/bin/sh\nexec '+shlex.quote(str(exe))+' --fullscreen "$@"\n');gaming.chmod(0o755)
    desktop_dir=home/'Desktop'
    if desktop_dir.is_dir():shutil.copyfile(path,desktop_dir/'APK Revival.desktop');(desktop_dir/'APK Revival.desktop').chmod(0o755)
    import configparser
    config=home/'.config';config.mkdir(parents=True,exist_ok=True)
    for name in ('mimeapps.list','kde-mimeapps.list'):
        mime=config/name;settings=configparser.ConfigParser(interpolation=None,strict=False);settings.optionxform=str
        if mime.exists():
            shutil.copyfile(mime,mime.with_name(mime.name+'.previous-'+str(time.time_ns())))
            settings.read(mime)
        if not settings.has_section('Default Applications'):settings.add_section('Default Applications')
        key='application/vnd.android.package-archive'
        existing=[item for item in settings.get('Default Applications',key,fallback='').split(';') if item and item!='apk-revival.desktop']
        settings.set('Default Applications',key,'apk-revival.desktop;'+(';'.join(existing)+';' if existing else ''))
        staged=mime.with_suffix('.apkr-new')
        with staged.open('w') as output:settings.write(output,space_around_delimiters=False)
        staged.replace(mime)
    from .steam import register
    steam=register(exe,home,icon=str(icon)) if register_steam else {'registered':False,'reason':'Host Steam process status is unavailable in the build sandbox. Close Steam and select Setup > Add to Steam in the installed application.'}
    return {'gaming_launcher':str(gaming),'steam':steam,'executable':str(exe),'desktop_file':str(path),'previous_install':str(prior) if source.resolve()!=target.resolve() else None}

def install_dialog():
    from PySide6.QtWidgets import QApplication,QMessageBox
    app=QApplication.instance() or QApplication(sys.argv)
    if QMessageBox.question(None,'Install APK Revival','Install APK Revival in your home folder and create an application-menu shortcut? No administrator password is needed. A previous installation is preserved.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return 0
    try:
        result=install();QMessageBox.information(None,'APK Revival installed','Open APK Revival from your application menu or open an APK from Dolphin.\n\n'+('The Steam launcher is registered.' if result['steam']['registered'] else result['steam']['reason']));return 0
    except Exception as e:QMessageBox.critical(None,'Installation failed',str(e));return 1


