"""A short human-guided Android gameplay test; each action calls real services."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog,QHBoxLayout,QVBoxLayout
from .ui import Worker,label,button
from ..meego.verification import GuidedTest

class MeegoTestDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.worker=None;self.closing=False;self.test=GuidedTest(window.service.store,window.current);self.setWindowTitle('Meego offline test');self.resize(760,430)
        box=QVBoxLayout(self);box.setContentsMargins(28,24,28,24);box.addWidget(label('Test Meego on Android','heading'));box.addWidget(label('This temporarily blocks external networking inside Android, while allowing local communication. Finish or cancel to restore the rules. Original installs and older saves stay untouched.','muted',True));self.instructions=label('Open the Android game alongside APK Revival. Start when ready.','readiness',True);box.addWidget(self.instructions,1)
        row=QHBoxLayout();self.cancel=button('Cancel test',self.reject);row.addWidget(self.cancel);row.addStretch();self.confirm=button('Start offline test',self.advance,'primary');row.addWidget(self.confirm);box.addLayout(row)
    def advance(self):
        if self.worker:return
        service=self.window.service
        def action(ctx):
            service.stop();ctx.step('Checking the current Android test stage')
            if self.test.stage=='new':return self.test.start(service.runtime_manager.ensure(service.settings.get('serial')))
            return {'village':self.test.confirm_village,'action':self.test.confirm_action,'loaded':self.test.confirm_loaded,'failure':self.test.confirm_failure,'recovered':self.test.confirm_recovered}[self.test.stage]()
        self.run(action)
    def run(self,action):
        self.confirm.setEnabled(False);self.worker=Worker(self.window.service,'Meego offline test',action,self);self.worker.succeeded.connect(self.completed);self.worker.failed.connect(lambda e:self.instructions.setText(e+'\nRetry or cancel.'));self.worker.finished.connect(self.job_finished);self.worker.start()
    def completed(self,result):
        self.instructions.setText(('Verified Offline. The tested scope is recorded under Advanced.' if result.get('passed') else 'Test incomplete. Review Advanced for the recorded results.') if isinstance(result,dict) else result);self.confirm.setText('Close' if self.test.finished else 'Confirm and continue')
    def job_finished(self):
        self.worker.deleteLater();self.worker=None;self.confirm.setEnabled(True)
        if self.closing:QTimer.singleShot(0,self.reject)
        elif self.test.finished:self.confirm.clicked.disconnect();self.confirm.clicked.connect(self.accept)
    def reject(self):
        if self.worker:self.closing=True;self.instructions.setText('Finishing the current operation before restoring networking.');return
        if not self.test.finished:
            self.closing=True;self.run(lambda ctx:self.test.finish(False,'User cancelled guided verification'));return
        self.window.refresh();super().reject()
    def closeEvent(self,event):
        if not self.test.finished or self.worker:event.ignore();self.reject()
        else:event.accept()
