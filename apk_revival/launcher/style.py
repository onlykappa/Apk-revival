STYLE='''
* { font-family: "DejaVu Sans"; font-size: 15px; color: #eaf2ef; }
QMainWindow, QWidget#base { background: #0d151a; }
QWidget#panel, QFrame#panel { background: #16242b; border-radius: 20px; }
QFrame#welcome { background: #111f26; border: 1px dashed #36554d; border-radius: 20px; }
QLabel { background: transparent; }
QLabel#muted { color: #a2b5bb; }
QLabel#heading { font-size: 32px; font-weight: 700; }
QLabel#brand { font-size: 24px; font-weight: 700; color: #9fe5c4; }
QLabel#tag { color: #9fe5c4; font-size: 13px; font-weight: 600; }
QLabel#readiness { font-size: 21px; font-weight: 600; }
QPushButton { background: #22353e; border: 2px solid transparent; border-radius: 12px; padding: 12px 18px; min-height: 23px; font-weight: 600; }
QPushButton:hover { background: #2d4752; }
QPushButton:focus { border: 2px solid #b9f1d7; }
QPushButton:disabled { color: #7c929a; background: #17272e; }
QPushButton#primary { background: #a5e8c9; color: #102b21; }
QPushButton#primary:hover { background: #c2f2df; }
QPushButton#primary:disabled { background: #365346; color: #8ba899; }
QPushButton#play { background: #a5e8c9; color: #102b21; font-size: 22px; padding: 16px; }
QPushButton#play:disabled { background: #365346; color: #8ba899; }
QPushButton#quiet { background: transparent; color: #afc1c6; }
QPushButton#card { text-align: left; padding: 0; background: #192b32; border-radius: 18px; min-height: 246px; max-height: 246px; }
QPushButton#card:checked { border: 2px solid #9fe5c4; }
QPushButton#card:focus { border: 3px solid #d2f7e5; }
QLineEdit, QComboBox, QPlainTextEdit { background: #101e25; border: 1px solid #34505a; border-radius: 10px; padding: 12px; selection-background-color: #426e60; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #9fe5c4; }
QPlainTextEdit { font-family: "DejaVu Sans Mono"; font-size: 13px; }
QWidget#grid_host { background: #0d151a; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #14242b; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #3b5963; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #1b3139; border: 0; border-radius: 5px; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #9fe5c4; border-radius: 5px; }
QDialog { background: #0d151a; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #1b3038; padding: 12px; border-radius: 7px; margin: 3px; }
QTabBar::tab:selected { background: #36594c; }
QCheckBox { spacing: 10px; padding: 9px; }
QCheckBox::indicator { width: 22px; height: 22px; }
'''
