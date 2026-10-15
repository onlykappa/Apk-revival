# Windows 11 (Fluent) dark palette. Controls stay at least 40 px tall for touch and
# controller use; focused controls swap 1 px borders for 2 px white focus rings
# with reduced padding, so focus never shifts the layout.
ACCENT='#60cdff'
STYLE='''
* { font-size: 14px; color: #ffffff; }
QMainWindow, QWidget#base, QWidget#nav_host { background: #202020; }
QWidget#content { background: #272727; border-top-left-radius: 8px; border-left: 1px solid #1a1a1a; border-top: 1px solid #1a1a1a; }
QWidget#page, QWidget#grid_host { background: #272727; }
QLabel { background: transparent; }
QLabel#muted { color: #c5c5c5; }
QLabel#caption { color: #9d9d9d; font-size: 12px; }
QLabel#heading, QLabel#title { font-size: 28px; font-weight: 600; }
QLabel#subtitle { font-size: 20px; font-weight: 600; }
QLabel#section { font-size: 14px; font-weight: 600; padding-top: 10px; }
QLabel#strong { font-weight: 600; }
QLabel#brand, QLabel#navtitle { font-size: 13px; font-weight: 400; color: #ffffff; }
QLabel#tag { color: #9d9d9d; font-size: 12px; }
QLabel#readiness { font-size: 15px; font-weight: 600; }
QLabel#meta_key { color: #9d9d9d; }
QLabel#meta_value { color: #ffffff; }
QLabel#pill_ok, QLabel#pill_info, QLabel#pill_warn { font-size: 12px; font-weight: 600; border-radius: 4px; padding: 2px 8px; }
QLabel#pill_ok { color: #6ccb5f; background: #2a3a28; }
QLabel#pill_info { color: #60cdff; background: #1f3440; }
QLabel#pill_warn { color: #fce100; background: #3d3816; }
QLabel#dot_ok { color: #6ccb5f; font-size: 11px; }
QLabel#dot_warn { color: #fce100; font-size: 11px; }

QFrame#card, QFrame#panel, QFrame#settingcard { background: #2b2b2b; border: 1px solid #1d1d1d; border-radius: 8px; }
QFrame#welcome { background: #2b2b2b; border: 1px dashed #4a4a4a; border-radius: 8px; }
QFrame#infobar { background: #2b2b2b; border: 1px solid #1d1d1d; border-radius: 6px; }
QFrame#infobar[severity="success"] { background: #393d1b; border-color: #2e3216; }
QFrame#infobar[severity="info"] { background: #1f3440; border-color: #1a2b35; }
QFrame#infobar[severity="warning"] { background: #433519; border-color: #382c14; }
QFrame#statusbar { background: #202020; border-top: 1px solid #1a1a1a; }
QFrame#divider { background: #1d1d1d; max-height: 1px; min-height: 1px; border: none; }
QFrame#footer { background: #202020; border-top: 1px solid #1d1d1d; }

QPushButton { background: #2d2d2d; border: 1px solid #3a3a3a; border-bottom-color: #303030; border-radius: 4px; padding: 8px 16px; min-height: 22px; color: #ffffff; }
QPushButton:hover { background: #323232; }
QPushButton:pressed { background: #272727; color: #c5c5c5; }
QPushButton:focus { border: 2px solid #ffffff; padding: 7px 15px; }
QPushButton:disabled { background: #2a2a2a; color: #6e6e6e; border-color: #303030; }
QPushButton#primary, QPushButton#play { background: #60cdff; border: 1px solid #6fd2ff; color: #000000; font-weight: 600; }
QPushButton#primary:hover, QPushButton#play:hover { background: #5bbde9; }
QPushButton#primary:pressed, QPushButton#play:pressed { background: #56a8cf; color: #1a1a1a; }
QPushButton#primary:focus, QPushButton#play:focus { border: 2px solid #ffffff; }
QPushButton#primary:disabled, QPushButton#play:disabled { background: #3a3a3a; color: #7a7a7a; border-color: #3a3a3a; }
QPushButton#play { font-size: 16px; }
QPushButton#quiet { background: transparent; border: 1px solid transparent; color: #ffffff; }
QPushButton#quiet:hover { background: #2d2d2d; }
QPushButton#quiet:focus { border: 2px solid #ffffff; }
QPushButton#quiet:disabled { color: #6e6e6e; background: transparent; }
QPushButton#nav { background: transparent; border: 1px solid transparent; border-radius: 4px; text-align: left; padding: 8px 12px; min-height: 20px; }
QPushButton#nav:hover { background: #2d2d2d; }
QPushButton#nav:checked { background: #2d2d2d; border-left: 3px solid #60cdff; padding-left: 10px; }
QPushButton#nav:focus { border: 2px solid #ffffff; padding: 7px 11px; }
QPushButton#nav:checked:focus { border: 2px solid #ffffff; border-left: 3px solid #60cdff; padding-left: 10px; }
QPushButton#card { text-align: left; padding: 0; min-height: 260px; max-height: 260px; min-width: 182px; max-width: 182px; background: #2b2b2b; border: 1px solid #1d1d1d; border-radius: 8px; }
QPushButton#card:hover { background: #323232; }
QPushButton#card:checked { background: #323232; border: 1px solid #60cdff; }
QPushButton#card:focus { border: 1px solid #ffffff; }

QLineEdit, QComboBox { background: #2d2d2d; border: 1px solid #3a3a3a; border-bottom: 1px solid #8a8a8a; border-radius: 4px; padding: 8px 12px; min-height: 22px; selection-background-color: #0078d4; }
QLineEdit:hover, QComboBox:hover { background: #323232; }
QLineEdit:focus { background: #1f1f1f; border-bottom: 2px solid #60cdff; padding-bottom: 7px; }
QComboBox:focus { border: 2px solid #ffffff; padding: 7px 11px; }
QComboBox:disabled, QLineEdit:disabled { color: #6e6e6e; background: #2a2a2a; border-bottom-color: #3a3a3a; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView { background: #2c2c2c; border: 1px solid #3a3a3a; selection-background-color: #383838; outline: none; padding: 4px; }
QPlainTextEdit { background: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 4px; padding: 8px; font-family: "DejaVu Sans Mono"; font-size: 13px; selection-background-color: #0078d4; }

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #5d5d5d; min-height: 30px; border-radius: 3px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: #8a8a8a; margin: 0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height: 0; background: none; }
QScrollBar:horizontal { height: 0; }
QProgressBar { background: #3a3a3a; border: 0; border-radius: 1px; min-height: 3px; max-height: 3px; }
QProgressBar::chunk { background: #60cdff; border-radius: 1px; }
QDialog { background: #2b2b2b; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: transparent; color: #c5c5c5; padding: 10px 14px; margin-right: 4px; border-bottom: 3px solid transparent; }
QTabBar::tab:hover { color: #ffffff; }
QTabBar::tab:selected { color: #ffffff; font-weight: 600; border-bottom: 3px solid #60cdff; }
QCheckBox { spacing: 10px; padding: 9px 0; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 4px; border: 1px solid #9d9d9d; background: #2b2b2b; }
QCheckBox::indicator:checked { background: #60cdff; border-color: #60cdff; }
QToolTip { background: #2c2c2c; color: #ffffff; border: 1px solid #3a3a3a; padding: 6px 8px; border-radius: 4px; }
QMessageBox, QInputDialog { background: #2b2b2b; }
'''

FONT_FAMILIES=['Segoe UI Variable Text','Segoe UI','Noto Sans','Cantarell','Ubuntu','DejaVu Sans']
