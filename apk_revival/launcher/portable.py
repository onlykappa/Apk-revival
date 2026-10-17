"""Single-game GUI used by V2 native portable exports."""
from __future__ import annotations
import json,pathlib,sys
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QDialog,QHBoxLayout,QLabel,QMessageBox,QPushButton,QVBoxLayout,QWidget
from ..backend import Backend
from ..runtime import WaydroidRuntime
from ..util import RevivalError,digest,read_json,safe_member
from .runtime_setup import RuntimeManager
from .tools_setup import configure
from .controller import Controller
from .ui import GameView,Worker,button,label
from .jobs import Jobs

class PortableSession:
    def __init__(self,root):
        self.root=pathlib.Path(root);self.jobs=Jobs();self.runtime_manager=RuntimeManager();self.android=None;configure()
        for name,sha in read_json(self.root/'hashes.json').items():
            safe_member(name)
            if digest(self.root/name)!=sha:raise RevivalError('Portable package integrity failed: '+name)
        self.bundle=read_json(self.root/'bundle.json');self.p=read_json(self.root/'profile.json')
        self.save_root=pathlib.Path.home()/'.local/share/apk-revival/portable-saves'/self.p['id']/self.bundle['path'];self.save_root.mkdir(parents=True,exist_ok=True)
    def play(self,ctx):
        if self.bundle['path']=='rebuild':return {'kind':'rebuild','save':str(self.save_root/'rebuild.json')}
        ctx.step('Connecting Android');serial=self.runtime_manager.ensure();r=WaydroidRuntime(serial);r.compatible(self.p);self.android=r;r.package=self.p['restoration'].get('client_package',self.p['analysis']['metadata']['package'])
        try:
            ctx.step('Checking the prepared client');installed=None
            try:
                paths=r.shell('pm','path',r.package).splitlines();base=next(x[8:] for x in paths if x.startswith('package:') and x.endswith('/base.apk'));installed=r.shell('sha256sum',base).split()[0]
            except (RevivalError,StopIteration,IndexError):pass
            if installed!=digest(self.root/'restored.apk'):r.adb('install','-r',self.root/'restored.apk',timeout=180)
            for i in self.bundle['supporting']:
                if i['role']=='obb':
                    dest='/sdcard/Android/obb/'+r.package;r.shell('mkdir','-p',dest);r.adb('push',self.root/i['file'],dest+'/'+i['name'],timeout=180)
            if self.bundle['path']=='local_backend':
                ctx.step('Starting and checking local services');port=self.bundle['backend_port']
                if self.p.get('adapter')=='tapquest-v1':r.backend=Backend(self.save_root/'tapquest.json',port).start()
                else:
                    from ..adapters import adapter,load_plugins
                    load_plugins(self.root/'plugins')
                    plugin=adapter(self.p)
                    if not hasattr(plugin,'start_backend'):raise RevivalError('Unsupported local backend')
                    r.backend=plugin.start_backend(self.save_root,self.root/'backend-data',port,apk=self.root/'restored.apk')
                r.adb('reverse','--no-rebind',f'tcp:{port}',f'tcp:{port}');r.forward_port=port;r.probe_backend()
            ctx.step('Launching Android');r.launch(self.p);return {'kind':'android'}
        except Exception:self.stop();raise
    def stop(self):
        try:
            if self.android:self.android.stop()
        finally:self.android=None
    def shutdown(self):
        try:self.stop()
        finally:self.runtime_manager.stop_owned_session()

class PortableWindow(QWidget):
    def __init__(self,root):
        super().__init__();self.setObjectName('base');self.session=PortableSession(root);self.worker=None;self.game=None;self.closing=False;self.setWindowTitle('APK Revival | '+self.session.p['title']);self.resize(1000,700);self.jobs=self.session.jobs;box=QVBoxLayout(self);box.setContentsMargins(40,30,40,30)
        box.addWidget(label(self.session.p['title'],'heading'));box.addWidget(label('Independent rebuild' if self.session.bundle['path']=='rebuild' else self.session.p['status'],'tag'));self.message=label('Select Play. This package does not include private save data.','muted',True);box.addWidget(self.message)
        controls=QHBoxLayout();self.play_button=button('Play',self.play,'play');self.stop_button=button('Stop',self.stop);controls.addWidget(self.play_button);controls.addWidget(self.stop_button);controls.addWidget(button('Android setup',self.setup));box.addLayout(controls);box.addStretch()
        self.controller=Controller(self,self.stop,self.setup)
    def play(self):
        if self.worker:return
        self.play_button.setEnabled(False);self.worker=Worker(self.session,'Play portable game',self.session.play,self);self.worker.update.connect(lambda job:self.message.setText(job['steps'][-1]['label'] if job['steps'] else 'Starting...'));self.worker.failed.connect(self.error);self.worker.succeeded.connect(self.started);self.worker.finished.connect(self.finished);self.worker.start()
    def started(self,result):
        self.message.setText('Playing. Android launch does not prove offline gameplay.')
        if result['kind']=='rebuild':
            self.game=QDialog(self);self.game.resize(1000,700);box=QVBoxLayout(self.game);box.setContentsMargins(0,0,0,0);view=GameView(result['save'],self.game.accept);box.addWidget(view);self.game_controller=Controller(self.game,self.game.accept,self.setup);self.game.finished.connect(lambda _:(self.play_button.setEnabled(True),self.game_controller.close()));self.game.show();self.game.activateWindow();view.collect.setFocus()
    def error(self,message):self.message.setText(message);self.play_button.setEnabled(True)
    def finished(self):
        self.worker.deleteLater();self.worker=None
        if self.closing:QTimer.singleShot(0,self.close)
    def stop(self):
        if self.worker:return
        if self.game:self.game.accept();self.game=None
        self.worker=Worker(self.session,'Stop portable game',lambda ctx:self.session.stop(),self);self.worker.succeeded.connect(lambda _:(self.play_button.setEnabled(True),self.message.setText('Stopped. Saved progress stays on this computer.')));self.worker.failed.connect(self.error);self.worker.finished.connect(self.finished);self.worker.start()
    def setup(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl('https://docs.waydro.id/usage/install-on-desktops'));self.message.setText('Configure Waydroid, then retry Play. With multiple Android devices, disconnect the ones you do not intend to use.')
    def closeEvent(self,event):
        if self.worker:self.closing=True;event.ignore();self.message.setText('Finishing the current operation before closing.');return
        if self.session.android:self.closing=True;event.ignore();self.stop();return
        self.controller.close();self.session.shutdown();event.accept()

