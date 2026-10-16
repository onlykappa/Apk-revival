"""Optional per-game modifications, separate from normal Play and game options."""
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class SkipWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, service, game, token, parent):
        super().__init__(parent)
        self.service, self.game, self.token = service, game, token

    def run(self):
        try:
            result = self.service.jobs.run('Mods: Skip timer', lambda ctx: self.service.skip_timer(self.game, self.token, ctx))
            self.succeeded.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class ModsDialog(QDialog):
    def __init__(self, service, game, parent=None):
        super().__init__(parent)
        self.service, self.game, self.worker = service, game, None
        self.setWindowTitle('Mods — Meego')
        self.resize(660, 370)
        box = QVBoxLayout(self)
        title = QLabel('Mods')
        title.setObjectName('title')
        box.addWidget(title)
        description = QLabel('Optional local game changes. Normal timers keep running until you choose Skip timer. No crystal skulls are charged.')
        description.setWordWrap(True)
        box.addWidget(description)
        self.enabled = QCheckBox('Enable Skip timer')
        box.addWidget(self.enabled)
        self.choices = QComboBox()
        self.choices.setMinimumHeight(44)
        box.addWidget(self.choices)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        scope = QLabel('Supports active construction, production preparation, classes, baby/child growth, item cooldowns and resource respawns. Discovery requires research points; dungeon actions and reward collection are unchanged. Return to the game after skipping; its next update refreshes the timer.')
        scope.setObjectName('caption')
        scope.setWordWrap(True)
        box.addWidget(scope)
        box.addStretch()
        buttons = QHBoxLayout()
        self.refresh_button = QPushButton('Refresh timers')
        self.skip_button = QPushButton('Skip timer')
        self.skip_button.setMinimumHeight(44)
        self.close_button = QPushButton('Close')
        for button in (self.refresh_button, self.skip_button, self.close_button):
            buttons.addWidget(button)
        box.addLayout(buttons)
        self.refresh_button.clicked.connect(self.refresh)
        self.skip_button.clicked.connect(self.skip)
        self.close_button.clicked.connect(self.reject)
        self.enabled.toggled.connect(self.update_controls)
        self.refresh()

    def update_controls(self):
        busy = self.worker is not None
        self.skip_button.setEnabled(not busy and self.enabled.isChecked() and self.choices.count() > 0)
        for widget in (self.refresh_button, self.close_button, self.enabled, self.choices):
            widget.setEnabled(not busy)

    def refresh(self):
        if self.worker is not None:
            return
        previous = self.choices.currentData()
        self.choices.clear()
        try:
            timers = self.service.mod_timers(self.game)
            for timer in timers:
                minutes, seconds = divmod(timer['seconds'], 60)
                self.choices.addItem(f"{timer['title']} — {minutes}m {seconds:02d}s", timer['token'])
            index = self.choices.findData(previous)
            if index >= 0:
                self.choices.setCurrentIndex(index)
            self.status.setText('Choose one timer to finish.' if timers else 'No supported active timers. Assign a worker or start a timed task, then refresh.')
        except Exception as error:
            self.status.setText(str(error))
        self.update_controls()

    def skip(self):
        if not self.skip_button.isEnabled():
            return
        self.worker = SkipWorker(self.service, self.game, self.choices.currentData(), self)
        self.worker.succeeded.connect(lambda title: self.status.setText('Skipped: ' + title))
        self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(self.finished_skip)
        self.status.setText('Finishing selected timer…')
        self.update_controls()
        self.worker.start()

    def finished_skip(self):
        message = self.status.text()
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.refresh()
        self.status.setText(message)

    def done(self, result):
        if self.worker is None:
            super().done(result)

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
        else:
            super().closeEvent(event)
