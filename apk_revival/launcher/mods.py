"""Optional per-game modifications, separate from normal Play and game options."""
from PySide6.QtCore import QThread, QTimer, Signal
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
        description = QLabel('Skip timer mod: use Skip timer beside the X in Meego’s baby, child and building countdown panels. Normal timers keep running until you click it. No crystal skulls are charged. The launcher picker below is optional.')
        description.setWordWrap(True)
        box.addWidget(description)
        self.enabled = QCheckBox('Enable launcher timer picker')
        box.addWidget(self.enabled)
        self.choices = QComboBox()
        self.choices.setMinimumHeight(44)
        self.choices.setPlaceholderText('Choose a timer to skip')
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
        self.choices.currentIndexChanged.connect(self.update_controls)
        self.refresh()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(lambda: self.refresh(automatic=True))
        self.refresh_timer.start()

    def update_controls(self):
        busy = self.worker is not None
        self.skip_button.setEnabled(not busy and self.enabled.isChecked() and bool(self.choices.currentData()))
        for widget in (self.refresh_button, self.close_button, self.enabled, self.choices):
            widget.setEnabled(not busy)

    def refresh(self, automatic=False):
        if self.worker is not None or (automatic and self.choices.view().isVisible()):
            return
        previous = self.choices.currentData()
        try:
            timers = self.service.mod_timers(self.game)
            self.choices.blockSignals(True)
            self.choices.clear()
            for timer in timers:
                minutes, seconds = divmod(timer['seconds'], 60)
                self.choices.addItem(f"{timer['title']} — {minutes}m {seconds:02d}s", timer['token'])
            index = self.choices.findData(previous)
            self.choices.setCurrentIndex(index)
            self.choices.blockSignals(False)
            if not automatic or not self.status.text():
                self.status.setText('Select a timer from the dropdown, then press Skip timer. The switch alone skips nothing.' if timers else 'No supported active timers. New tasks appear automatically while this menu is open.')
            elif previous and index < 0:
                self.status.setText('The selected task finished or changed. Choose another timer to skip.')
            elif timers and self.status.text().startswith(('No supported', 'Game is updating')):
                self.status.setText('New timers available. Select one from the dropdown, then press Skip timer.')
        except Exception as error:
            self.choices.blockSignals(False)
            self.choices.clear()
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
            self.refresh_timer.stop()
            super().done(result)

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
        else:
            super().closeEvent(event)
