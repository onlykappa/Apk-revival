from __future__ import annotations
import json,pathlib,sys,time,traceback
from PySide6.QtCore import QEvent,QPoint,QRect,QRectF,QSize,Qt,QThread,QTimer,Signal
from PySide6.QtGui import QColor,QDesktopServices,QFont,QFontMetrics,QLinearGradient,QPainter,QPainterPath,QPen,QPixmap,QIcon
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication,QAbstractButton,QCheckBox,QComboBox,QDialog,QFileDialog,QFrame,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QLayout,QSizePolicy,QMainWindow,QMessageBox,QInputDialog,QPlainTextEdit,QProgressBar,QPushButton,QScrollArea,QStackedWidget,QTabWidget,QVBoxLayout,QWidget
from ..analysis import markdown
from ..backend import Progress
from ..store import Store
from ..util import RevivalError,now
from .controller import Controller,spatial_focus
from .icons import icon,pixmap
from .metadata import details,friendly_date,icon_path,subtitle
from .presentation import CONTROL_PROFILES,readiness
from .service import Launcher
from .style import ACCENT,FONT_FAMILIES,STYLE
from . import tools_setup

def brand_asset():
    return pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources/apk-revival-logo.png'

PATH_NAMES={'offline_patch':'Preserve the APK offline','local_backend':'Use a local backend','rebuild':'Create a separate rebuild'}
TILE_WIDTH=184;TILE_HEIGHT=262;TILE_GAP=12
STATUS_PILLS={'Restoration work needed':('Not supported yet','pill_warn'),'Additional files needed':('Files needed','pill_warn'),'Imported':('Checking','pill_warn'),'Preparation needs repair':('Needs repair','pill_warn')}

def label(text,kind=None,wrap=False):
    w=QLabel(text)
    if kind:w.setObjectName(kind)
    w.setWordWrap(wrap)
    if wrap:
        policy=w.sizePolicy();policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored);w.setSizePolicy(policy)
    return w

def button(text,action=None,kind=None,icon_name=None):
    w=QPushButton(text)
    if kind:w.setObjectName(kind)
    if icon_name:w.setIcon(icon(icon_name,'#000000' if kind in ('primary','play') else '#ffffff',18));w.setIconSize(QSize(18,18))
    if action:w.clicked.connect(action)
    return w

def restyle(widget):
    widget.style().unpolish(widget);widget.style().polish(widget)

def icon_label(name,size=20,color='#ffffff'):
    w=QLabel();w.setPixmap(pixmap(name,color,size));w.setFixedSize(size+4,size+4);w.setAlignment(Qt.AlignmentFlag.AlignCenter);return w

class SettingCard(QFrame):
    """Height follows wrapped description text at the card's real width."""
    def sizeHint(self):
        hint=super().sizeHint();width=self.width() if self.width()>100 else hint.width()
        return QSize(hint.width(),self.heightForWidth(width) if self.hasHeightForWidth() else hint.height())

def setting_card(icon_name,title,description,*controls):
    """A Windows Settings style row: icon, title and description, controls on the right."""
    card=SettingCard();card.setObjectName('settingcard');row=QHBoxLayout(card);row.setContentsMargins(18,14,18,14);row.setSpacing(16)
    row.addWidget(icon_label(icon_name),0,Qt.AlignmentFlag.AlignVCenter)
    text=QVBoxLayout();text.setSpacing(2);text.addStretch();text.addWidget(label(title,'strong'))
    note=description if isinstance(description,QLabel) else label(description,'caption',True)
    note.setWordWrap(True);note.setMinimumWidth(160);text.addWidget(note);text.addStretch();row.addLayout(text,1)
    for control in controls:row.addWidget(control,0,Qt.AlignmentFlag.AlignVCenter)
    card.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
    return card

def dialog_shell(dialog,title,description=None):
    """Windows content dialog: title and body on top, a darker footer holding the buttons."""
    outer=QVBoxLayout(dialog);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
    body_host=QWidget();body=QVBoxLayout(body_host);body.setContentsMargins(24,22,24,20);body.setSpacing(12);body.addWidget(label(title,'subtitle'))
    if description:body.addWidget(label(description,'muted',True))
    outer.addWidget(body_host,1)
    footer_host=QFrame();footer_host.setObjectName('footer');footer=QHBoxLayout(footer_host);footer.setContentsMargins(24,18,24,18);footer.setSpacing(8);outer.addWidget(footer_host)
    return body,footer

class Worker(QThread):
    update=Signal(object);succeeded=Signal(object);failed=Signal(str)
    def __init__(self,service,title,operation,parent=None):super().__init__(parent);self.service=service;self.title=title;self.operation=operation
    def run(self):
        try:self.succeeded.emit(self.service.jobs.run(self.title,self.operation,self.update.emit))
        except Exception as e:self.failed.emit(str(e))

PALETTES=[('#0f6cbd','#0a3d6b'),('#5c2e91','#321a52'),('#107c41','#0a4a27'),('#c239b3','#6b1f63'),('#ca5010','#6e2c09'),('#038387','#02494b')]

class GameArt(QWidget):
    """Game icon from the APK, or a generated Windows-style tile with initials."""
    def __init__(self,size=96,parent=None):
        super().__init__(parent);self.title='';self.seed='';self.image=None;self.logo=False;self.setFixedSize(size,size)
    def set_game(self,title,seed,image=None,logo=False):
        self.title=title;self.seed=seed;self.image=image if image and not image.isNull() else None;self.logo=logo;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        side=self.width()*.86;r=QRectF((self.width()-side)/2,(self.height()-side)/2,side,side);radius=side*.2
        if self.image or self.logo:
            source=self.image or QPixmap(str(brand_asset()))
            scaled=source.scaled(r.size().toSize()*2,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation);scaled.setDevicePixelRatio(2)
            p.drawPixmap(int(r.x()+(r.width()-scaled.width()/2)/2),int(r.y()+(r.height()-scaled.height()/2)/2),scaled);return
        clip=QPainterPath();clip.addRoundedRect(r,radius,radius)
        index=int(self.seed[:2],16)%len(PALETTES) if len(self.seed)>=2 and all(c in '0123456789abcdef' for c in self.seed[:2]) else 0
        a,b=PALETTES[index];gradient=QLinearGradient(r.topLeft(),r.bottomRight());gradient.setColorAt(0,QColor(a));gradient.setColorAt(1,QColor(b));p.fillPath(clip,gradient)
        words=[w for w in ''.join(c if c.isalnum() else ' ' for c in self.title).split() if w]
        initials=(words[0][0]+(words[1][0] if len(words)>1 else '')).upper() if words else 'A'
        font=QFont(QApplication.font());font.setPixelSize(int(side*.4));font.setWeight(QFont.Weight.DemiBold);p.setFont(font);p.setPen(QColor('#ffffff'))
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,initials)

class GameCard(QPushButton):
    def __init__(self,p,selected,action,image=None):
        super().__init__();self.setObjectName('card');self.setCheckable(True);self.setChecked(selected);self.ensurePolished();self.setFixedSize(TILE_WIDTH,TILE_HEIGHT);self.setAccessibleName(p['title']);self.setToolTip(p['title']);self.clicked.connect(action)
        box=QVBoxLayout(self);box.setContentsMargins(14,14,14,12);box.setSpacing(4)
        art=GameArt(TILE_WIDTH-28);art.set_game(p['title'],p['id'],image);art.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);box.addWidget(art);box.addSpacing(6)
        title=label(QFontMetrics(QApplication.font()).elidedText(p['title'],Qt.TextElideMode.ElideRight,TILE_WIDTH-30),'strong');box.addWidget(title)
        detail=label(subtitle(p),'caption');box.addWidget(detail)
        ready=readiness(p);text,kind=STATUS_PILLS.get(ready['label'],('Ready to play','pill_ok') if ready['play'] else ('Needs preparing','pill_info') if ready['prepare'] else (ready['label'],'pill_warn'))
        pill=label(text,kind);row=QHBoxLayout();row.setContentsMargins(0,2,0,0);row.addWidget(pill);row.addStretch();box.addLayout(row)
        for w in (title,detail,pill):w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        box.addStretch()

class ImportDialog(QDialog):
    def __init__(self,apk=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Add game');self.resize(640,560);self.support=[]
        box,footer=dialog_shell(self,'Add a game','Choose the game file: an APK, or an XAPK, APKS or APKM bundle. Extra files are optional and help with games that need them.')
        box.addWidget(label('Game file','strong'))
        row=QHBoxLayout();self.apk=QLineEdit(apk or '');self.apk.setPlaceholderText('Choose an .apk, .xapk, .apks or .apkm file');row.addWidget(self.apk,1);row.addWidget(button('Browse',self.pick_apk,None,'folder'));box.addLayout(row)
        box.addSpacing(6);box.addWidget(label('Extra files (optional)','strong'));box.addWidget(label('Expansion files (OBB), split APKs, asset folders, logs or save files.','caption',True))
        self.files=QPlainTextEdit();self.files.setReadOnly(True);self.files.setPlaceholderText('No extra files added');self.files.setMinimumHeight(90);box.addWidget(self.files,1)
        actions=QGridLayout();actions.setSpacing(8)
        actions.addWidget(button('OBBs / split APKs',lambda:self.pick_support(None)),0,0);actions.addWidget(button('Asset files',lambda:self.pick_support('asset')),0,1);actions.addWidget(button('Asset folder',self.pick_folder),0,2);actions.addWidget(button('Logs',lambda:self.pick_support('log')),1,0);actions.addWidget(button('Save files',lambda:self.pick_support('save')),1,1);box.addLayout(actions)
        box.addWidget(label('Your original files are copied and never changed. Private saves and logs are left out of exports.','caption',True))
        footer.addStretch();self.add=button('Add game',self.accept,'primary');self.add.setMinimumWidth(130);footer.addWidget(self.add);cancel=button('Cancel',self.reject);cancel.setMinimumWidth(130);footer.addWidget(cancel)
    def pick_apk(self):
        file,_=QFileDialog.getOpenFileName(self,'Choose a game','','Android games (*.apk *.xapk *.apks *.apkm)')
        if file:self.apk.setText(file)
    def pick_support(self,role):
        files,_=QFileDialog.getOpenFileNames(self,'Add supporting files')
        self.support.extend((role,f) if role else f for f in files);self.refresh()
    def pick_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Add asset folder')
        if path:self.support.append(('asset',path));self.refresh()
    def refresh(self):self.files.setPlainText('\n'.join((x[0]+': '+x[1]) if isinstance(x,tuple) else x for x in self.support))

class GameView(QWidget):
    def __init__(self,save,back):
        super().__init__();self.setObjectName('page');self.progress=Progress(save);box=QVBoxLayout(self);box.setContentsMargins(36,28,36,36)
        top=QHBoxLayout();top.addWidget(button('Back to library',back,None,'library'));top.addStretch();top.addWidget(label('Independent desktop rebuild','tag'));box.addLayout(top);box.addStretch()
        card=QFrame();card.setObjectName('card');card.setMaximumWidth(560);inner=QVBoxLayout(card);inner.setContentsMargins(40,36,40,36);inner.setSpacing(14)
        inner.addWidget(label('Tap Quest','title'),alignment=Qt.AlignmentFlag.AlignCenter)
        self.state=label('','subtitle');inner.addWidget(self.state,alignment=Qt.AlignmentFlag.AlignCenter);self.collect=button('Collect coin',self.action,'play');self.collect.setMinimumSize(320,48);inner.addWidget(self.collect,alignment=Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(label('Every 10 coins raises your level. Progress saves after every action.','muted'),alignment=Qt.AlignmentFlag.AlignCenter)
        box.addWidget(card,alignment=Qt.AlignmentFlag.AlignCenter);box.addStretch();self.refresh();self.collect.setFocus()
    def refresh(self):
        state=self.progress.get();self.state.setText(f'Coins: {state["coins"]}     Level: {state["level"]}')
    def action(self):self.progress.collect();self.refresh()

class Window(QMainWindow):
    def __init__(self,store=None,fullscreen=False,close_after_game=False):
        # close_after_game: started for one game (a Steam game shortcut). Closing
        # once it ends hands control back to Steam without another click.
        self.close_after_game=close_after_game;self.game_started=False
        super().__init__();self.service=Launcher(store or Store());self.current=None;self.worker=None;self.monitor_worker=None;self.cards=[];self.last_job=None;self.rebuild_view=None;self.active_page='library';self.closing=False;self.repair_games=set();self.focus_play_after_prepare=False;self.art_cache={};self.columns=0;self.queued=None
        self.setWindowTitle('APK Revival');self.setWindowIcon(QIcon(str(brand_asset())));self.resize(1280,800);self.setMinimumSize(1000,650);self.setAcceptDrops(True)
        root=QWidget();root.setObjectName('base');self.setCentralWidget(root);outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        outer.addWidget(self.navigation())
        content=QWidget();content.setObjectName('content');content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True);column=QVBoxLayout(content);column.setContentsMargins(0,0,0,0);column.setSpacing(0);outer.addWidget(content,1)
        self.stack=QStackedWidget();column.addWidget(self.stack,1);self.library=self.library_page();self.stack.addWidget(self.library);self.setup=self.setup_page();self.stack.addWidget(self.setup)
        self.bar=QProgressBar();self.bar.setRange(0,0);self.bar.setTextVisible(False);self.bar.hide();column.addWidget(self.bar)
        self.feedback=QFrame();self.feedback.setObjectName('statusbar');feedback=QHBoxLayout(self.feedback);feedback.setContentsMargins(20,8,20,8);feedback.setSpacing(12);self.message=label('Ready. Add a game or try the included desktop demo.','muted',True);feedback.addWidget(self.message,1);self.cancel_button=button('Cancel task',self.cancel,'quiet');feedback.addWidget(self.cancel_button);self.cancel_button.hide()
        feedback.addWidget(label('A  Select    B  Back    D-pad  Move','caption'));column.addWidget(self.feedback)
        self.controller=Controller(self,self.back,self.options);QApplication.instance().installEventFilter(self);self.set_page('library');self.refresh()
        self.monitor_timer=QTimer(self);self.monitor_timer.timeout.connect(self.monitor);self.monitor_timer.start(5000)
        if fullscreen or self.service.settings.get('fullscreen'):self.showFullScreen()
        QTimer.singleShot(80,self.check_runtime);QTimer.singleShot(0,self.initial_focus)
    def initial_focus(self):
        target=next((c for c in self.cards if c.isChecked()),None) or self.add_button
        if target.isVisible():target.setFocus()
    def navigation(self):
        host=QWidget();host.setObjectName('nav_host');host.setFixedWidth(232);self.nav_host=host;self.compact=False;box=QVBoxLayout(host);box.setContentsMargins(8,14,8,14);box.setSpacing(4)
        brand=QHBoxLayout();brand.setContentsMargins(12,0,0,10);brand.setSpacing(10);mark=QLabel();mark.setPixmap(QPixmap(str(brand_asset())).scaled(22,22,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));mark.setFixedSize(22,22);brand.addWidget(mark);self.nav_title=label('APK Revival','navtitle');brand.addWidget(self.nav_title);brand.addStretch();box.addLayout(brand)
        self.library_nav=button('Library',lambda:self.back_to_library(),'nav','library');self.setup_button=button('Setup',self.show_setup,'nav','setup');self.updates_button=button('Updates',self.show_updates,'nav','updates')
        for b in (self.library_nav,self.setup_button,self.updates_button):b.setCheckable(True);b.setIconSize(QSize(18,18));box.addWidget(b)
        box.addStretch()
        status=QHBoxLayout();status.setContentsMargins(12,0,0,0);status.setSpacing(8);self.connection_dot=label('●','dot_warn');status.addWidget(self.connection_dot);self.connection_label=label('Android: not checked','caption');status.addWidget(self.connection_label);self.connection_dot.setToolTip('Android connection');status.addStretch();box.addLayout(status)
        from .. import __version__
        version=label('Version '+__version__,'caption');version.setContentsMargins(12,2,0,6);box.addWidget(version);self.version_label=version
        self.fullscreen_button=button('Fullscreen',self.toggle_fullscreen,'nav','fullscreen');self.fullscreen_button.setIconSize(QSize(18,18));box.addWidget(self.fullscreen_button)
        return host
    def set_compact(self,compact):
        """Collapse navigation to icons on narrow windows, like Windows' compact pane."""
        if compact==self.compact:return
        self.compact=compact;self.nav_host.setFixedWidth(60 if compact else 232)
        for b,text in ((self.library_nav,'Library'),(self.setup_button,'Setup'),(self.updates_button,'Updates'),(self.fullscreen_button,'Exit fullscreen' if self.isFullScreen() else 'Fullscreen')):
            b.setText('' if compact else text);b.setToolTip(text if compact else '')
        for w in (self.nav_title,self.connection_label,self.version_label):w.setVisible(not compact)
    def resizeEvent(self,event):
        self.set_compact(event.size().width()<1180);super().resizeEvent(event)
    def set_page(self,name):
        for b,page in ((self.library_nav,'library'),(self.setup_button,'setup'),(self.updates_button,'updates')):b.setChecked(page==name)
    def back_to_library(self):
        if self.active_page=='game':return
        self.return_to_library()
    def library_page(self):
        page=QWidget();page.setObjectName('page');layout=QVBoxLayout(page);layout.setContentsMargins(36,28,28,16);layout.setSpacing(18)
        head=QHBoxLayout();head.setSpacing(8);titles=QVBoxLayout();titles.setSpacing(0);titles.addWidget(label('Library','title'));self.library_count=label('','caption');titles.addWidget(self.library_count);head.addLayout(titles);head.addStretch()
        self.search=QLineEdit();self.search.setPlaceholderText('Search your games');self.search.setFixedWidth(260);self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.refresh);head.addWidget(self.search,0,Qt.AlignmentFlag.AlignVCenter)
        self.demo_button=button('Try desktop demo',self.demo,'quiet','spark');head.addWidget(self.demo_button,0,Qt.AlignmentFlag.AlignVCenter)
        self.add_button=button('Add game',self.add_game,'primary','add');head.addWidget(self.add_button,0,Qt.AlignmentFlag.AlignVCenter);layout.addLayout(head)
        body=QHBoxLayout();body.setSpacing(20);layout.addLayout(body,1)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.grid_host=QWidget();self.grid_host.setObjectName('grid_host');self.grid=QGridLayout(self.grid_host);self.grid.setContentsMargins(2,2,2,2);self.grid.setSpacing(TILE_GAP);self.grid.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft);self.scroll.setWidget(self.grid_host);body.addWidget(self.scroll,1)
        self.details=QFrame();self.details.setObjectName('panel');right=QVBoxLayout(self.details);right.setContentsMargins(22,22,22,20);right.setSpacing(12)
        top=QHBoxLayout();top.setSpacing(16);self.hero=GameArt(88);self.hero.set_game('APK Revival','demo',logo=True);top.addWidget(self.hero,0,Qt.AlignmentFlag.AlignTop)
        names=QVBoxLayout();names.setSpacing(2);self.game_title=label('Your next revival','subtitle',True);names.addWidget(self.game_title);self.game_kind=label('Local library','caption',True);names.addWidget(self.game_kind);top.addLayout(names,1);top.setAlignment(names,Qt.AlignmentFlag.AlignTop);right.addLayout(top)
        self.infobar=QFrame();self.infobar.setObjectName('infobar');info=QVBoxLayout(self.infobar);info.setContentsMargins(14,10,14,12);info.setSpacing(3)
        self.readiness_label=label('Start with an APK','readiness',True);info.addWidget(self.readiness_label);self.description=label('Choose a game file. APK Revival checks what it needs and keeps the original untouched.','muted',True);info.addWidget(self.description);right.addWidget(self.infobar)
        self.prepare_button=button('Prepare game',self.prepare,'play','package');self.prepare_button.setMinimumHeight(46);right.addWidget(self.prepare_button);self.play_button=button('Play',self.play,'play','play');self.play_button.setMinimumHeight(46);right.addWidget(self.play_button);self.stop_button=button('Stop game',self.stop,None,'stop');self.stop_button.setMinimumHeight(46);right.addWidget(self.stop_button)
        self.options_button=button('Game options',self.options,None,'more');right.addWidget(self.options_button)
        self.mods_button=button('Mods',self.show_mods);right.addWidget(self.mods_button)
        self.divider=QFrame();self.divider.setObjectName('divider');right.addWidget(self.divider);self.details_heading=label('Details','strong');right.addWidget(self.details_heading)
        self.meta=QGridLayout();self.meta.setHorizontalSpacing(16);self.meta.setVerticalSpacing(7);self.meta.setColumnStretch(1,1);right.addLayout(self.meta)
        right.addStretch();controls=QHBoxLayout();controls.setSpacing(8);controls.addWidget(icon_label('gamepad',16,'#9d9d9d'),0,Qt.AlignmentFlag.AlignTop);self.controls_label=label('Touch, trackpad and controller-aware browsing.','caption',True);controls.addWidget(self.controls_label,1);right.addLayout(controls)
        side=QScrollArea();side.setWidgetResizable(True);side.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);side.setFixedWidth(380);side.setWidget(self.details);self.details_scroll=side;body.addWidget(side)
        return page
    def setup_page(self):
        page=QWidget();page.setObjectName('page');box=QVBoxLayout(page);box.setSpacing(4);box.setContentsMargins(36,28,36,28)
        box.addWidget(label('Setup','title'));box.addWidget(label('Everything APK Revival needs to prepare and play your games.','muted',True));box.addSpacing(10)
        box.addWidget(label('Preparation tools','section'))
        self.tools_label=label('Checking tools...','caption',True);self.install_tools_button=button('Install preparation tools',self.install_tools,'primary')
        box.addWidget(setting_card('package','Preparation tools',self.tools_label,self.install_tools_button))
        box.addSpacing(6);box.addWidget(label('Android','section'))
        self.runtime_label=label('Check for an existing Waydroid installation.','caption',True)
        box.addWidget(setting_card('phone','Android connection',self.runtime_label,button('Check again',self.check_runtime,None,'refresh')))
        self.devices=QComboBox();self.devices.setAccessibleName('Android device');self.devices.setMinimumWidth(240);self.devices.currentIndexChanged.connect(self.device_selected)
        box.addWidget(setting_card('link','Android device','Which connected Android environment to use.',self.devices))
        box.addWidget(setting_card('play','Start Android','Starts your existing Waydroid session. Starting the container asks for your administrator password.',button('Start Android',self.start_android),button('Start container',self.start_container)))
        box.addWidget(setting_card('setup','Runtime startup access','One-time administrator setup allows the existing main runtime to start without repeated password prompts.',button('Enable password-free startup',self.enable_runtime_access)))
        box.addWidget(setting_card('refresh','Runtime recovery','Restart the owned Android runtime while preserving saves and controls.',button('Restart Android',self.restart_android)))
        box.addWidget(setting_card('info','Input diagnostics','Capture a touchscreen or mouse comparison without changing settings.',button('Capture input diagnostics',self.input_diagnostics)))
        box.addWidget(setting_card('window','Open Android','Shows the full Android screen, for example to approve USB debugging.',button('Open Android',self.open_android_ui)))
        self.address=QLineEdit();self.address.setPlaceholderText('Android IP address');self.address.setFixedWidth(200)
        box.addWidget(setting_card('link','Connect by IP address','Only needed when Android is running but was not found automatically.',self.address,button('Connect',self.manual_connect)))
        box.addWidget(setting_card('info','Install Waydroid','Waydroid provides Android on Linux. It is installed separately; APK Revival never changes system protections.',button('Installation guide',self.installation_guide)))
        from .updater import Updater
        self.updater=Updater();self.pending_update=None
        box.addSpacing(6);box.addWidget(label('Updates','section'))
        self.update_label=label('Updates install automatically and preserve games and saves.','caption',True)
        box.addWidget(setting_card('updates','APK Revival updates',self.update_label,button('Check for updates',self.check_updates,'primary')))
        box.addWidget(setting_card('download','Install from a file','Install an official Linux update downloaded from GitHub releases.',button('Install downloaded update',self.install_downloaded_update),button('Open releases',lambda:QDesktopServices.openUrl(QUrl(self.updater_url())),'quiet')))
        box.addWidget(setting_card('key','Private releases','Optional read-only GitHub token. Kept in memory until you close the app.',button('GitHub access',self.github_access)))
        box.addSpacing(6);box.addWidget(label('Desktop and Steam','section'))
        box.addWidget(setting_card('window','Desktop shortcut','Adds APK Revival to your applications menu.',button('Install desktop shortcut',self.install_shortcut)))
        box.addWidget(setting_card('gamepad','Add to Steam','Launch APK Revival from Gaming Mode as a non-Steam game.',button('Add to Steam',self.steam_help)))
        box.addSpacing(12);box.addWidget(label('SteamOS needs a compatible kernel and Wayland setup. Host installation is guided; system protections are not changed automatically.','caption',True));box.addStretch()
        self.setup_scroll=QScrollArea();self.setup_scroll.setWidgetResizable(True);self.setup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.setup_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn);self.setup_scroll.setWidget(page);return self.setup_scroll
    def artwork(self,p):
        if p['id'] not in self.art_cache:
            path=icon_path(self.service.store,p);image=QPixmap(str(path)) if path else None
            self.art_cache[p['id']]=image if image and not image.isNull() else None
        return self.art_cache[p['id']]
    def layout_cards(self):
        width=self.scroll.viewport().width();columns=max(1,(width-4+TILE_GAP)//(TILE_WIDTH+TILE_GAP))
        items=[self.grid.itemAt(i).widget() for i in range(self.grid.count())]
        for w in items:self.grid.removeWidget(w)
        for index,card in enumerate(self.cards):self.grid.addWidget(card,index//columns,index%columns)
        for w in items:
            if w not in self.cards:self.grid.addWidget(w,0,0,1,max(1,columns))
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft if self.cards else Qt.AlignmentFlag.AlignTop)
        self.columns=columns
    def refresh(self,*_):
        old_focus=QApplication.focusWidget();focus_game=old_focus.property('game_id') if old_focus else None
        self.cards=[]
        while self.grid.count():
            item=self.grid.takeAt(0)
            widget=item.widget()
            if widget:widget.hide();widget.setParent(None);widget.deleteLater()
        games=self.service.store.games();query=self.search.text().casefold();filtered=[p for p in games if query in p['title'].casefold()]
        if self.current not in {p['id'] for p in games}:self.current=None
        if self.service.store.last_library_errors:self.message.setText('Some saved library entries could not be read. See the library error report in diagnostics.')
        self.library_count.setText(f'{len(games)} game'+('s' if len(games)!=1 else '') if games else 'No games yet')
        if not self.current and games:self.current=games[0]['id']
        for p in filtered:
            card=GameCard(p,p['id']==self.current,lambda checked=False,game=p['id']:self.select(game),self.artwork(p));card.setProperty('game_id',p['id']);self.cards.append(card)
            if p['id']==focus_game:card.setFocus()
        if not filtered:
            if games:self.grid.addWidget(label('No games match your search.','muted'),0,0)
            else:
                welcome=QFrame();welcome.setObjectName('welcome');welcome.setMinimumHeight(420);box=QVBoxLayout(welcome);box.setContentsMargins(28,28,28,28);box.setSpacing(10);box.addStretch();mark=QLabel();mark.setPixmap(QPixmap(str(brand_asset())).scaled(88,88,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));box.addWidget(mark,alignment=Qt.AlignmentFlag.AlignCenter);box.addWidget(label('Bring your games back','subtitle'),alignment=Qt.AlignmentFlag.AlignCenter);copy=label('Drop an APK here or choose Add game to start your library.\nOr try Tap Quest, included and ready to play.','muted',True);copy.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(copy);box.addStretch();self.grid.addWidget(welcome,0,0)
        self.layout_cards();self.update_details();self.update_tools()
    def select(self,game):
        self.current=game
        for c in self.cards:c.setChecked(c.property('game_id')==game)
        self.update_details()
    def profile(self):
        if not self.current:raise RevivalError('Add or select a game first.')
        return self.service.store.load(self.current,check=False)
    def show_metadata(self,rows):
        while self.meta.count():
            item=self.meta.takeAt(0);widget=item.widget()
            if widget:widget.hide();widget.setParent(None);widget.deleteLater()
        for index,(key,value) in enumerate(rows):
            k=label(key,'meta_key');v=label(value,'meta_value',True);v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);self.meta.addWidget(k,index,0,Qt.AlignmentFlag.AlignTop);self.meta.addWidget(v,index,1)
        self.details_heading.setVisible(bool(rows))
    def update_details(self):
        self.mods_button.hide()
        if not self.current:
            for w in [self.play_button,self.prepare_button,self.stop_button]:w.hide();w.setEnabled(False)
            self.options_button.setEnabled(False);self.options_button.hide();self.divider.hide();self.show_metadata([])
            return
        p=self.profile();ready=readiness(p,self.service.runtime_manager.last.get('ready',False))
        artifact=p.get('restoration',{}).get('artifact')
        missing=bool(artifact and not (self.service.store.directory(p['id'])/artifact).is_file())
        if missing or p['id'] in self.repair_games:
            ready={'label':'Preparation needs repair','detail':'The prepared file is missing or damaged. Select Prepare game to repair it. Your saves are preserved.','prepare':True,'play':False}
        self.game_title.setText(p['title'] if len(p['title'])<40 else p['title'][:38]+'...');self.game_title.setToolTip(p['title']);self.hero.set_game(p['title'],p['id'],self.artwork(p))
        self.game_kind.setText(('Independent rebuild' if p['restoration']['path']=='rebuild' else 'Android game')+('  ·  self-authored demo' if p['analysis'] and p['analysis']['fixture'] else ''));self.readiness_label.setText(ready['label']);self.description.setText(ready['detail'])
        self.infobar.setProperty('severity','success' if ready['play'] else 'info' if ready['prepare'] else 'warning');restyle(self.infobar)
        self.show_metadata(details(p))
        self.options_button.show();self.divider.show()
        busy=bool(self.worker and self.worker.isRunning());active=self.service.active
        # Play can open an original APK; Prepare can create a restored copy.
        # Preparation state lives in the saved
        # profile, not in the current Android connection or launcher UI session.
        playing_here=bool(active and active['game']==p['id'])
        self.mods_button.setVisible(p.get('adapter')=='meego-1.32')
        self.mods_button.setEnabled(bool(not busy and playing_here))
        self.prepare_button.setVisible(bool(ready['prepare'] and not active))
        self.play_button.setVisible(bool(ready['play'] and not active))
        self.stop_button.setVisible(playing_here)
        self.prepare_button.setEnabled(bool(not busy and not active and ready['prepare']))
        self.play_button.setEnabled(bool(not busy and not active and ready['play']))
        self.stop_button.setEnabled(bool(not busy and playing_here))
        self.options_button.setEnabled(bool(not busy and not active))
        control=CONTROL_PROFILES.get(p.get('adapter'),{'description':'Controls are unknown until this game is investigated.'});self.controls_label.setText('Controls: A / Enter collects. B / Esc returns.' if p['restoration']['path']=='rebuild' else 'Controls: touch or trackpad.' if p.get('adapter') in {'tapquest-v1','meego-1.32'} else 'Controls need game-specific investigation.')
    def show_mods(self):
        if not self.current:return
        from .mods import ModsDialog
        ModsDialog(self.service,self.current,self).exec()
    def submit(self,title,operation,callback=None):
        if self.worker:
            # One background task runs at a time. Never drop a request silently:
            # run the most recent one as soon as the current task finishes.
            self.queued=(title,operation,callback);self.message.setText(title+' will start when '+self.worker.title[0].lower()+self.worker.title[1:]+' finishes.');return
        if self.monitor_worker and self.monitor_worker.isRunning():
            # Status checks share the serialized service lock. Queue button
            # actions instead of making Stop/Play fail depending on timing.
            if not getattr(self,'pending_submission',None):self.pending_submission=(title,operation,callback)
            self.message.setText('Finishing the current status check...');return
        self.worker=Worker(self.service,title,operation,self);worker=self.worker;self.callback=callback;worker.update.connect(self.progress);worker.succeeded.connect(self.completed);worker.failed.connect(self.failed);worker.finished.connect(lambda owned=worker:self.job_finished(owned));self.bar.show();self.cancel_button.show();self.add_button.setEnabled(False);self.demo_button.setEnabled(False);worker.start();self.update_details()
    def progress(self,job):
        self.last_job=job;step=job['steps'][-1]['label'] if job['steps'] else job['label'];self.message.setText(step+('...' if job['state']=='running' else ''))
    def completed(self,result):
        self.message.setText('Completed.');self.refresh()
        if self.active_page=='game' and not self.service.active:self.return_to_library()
        if self.callback:self.callback(result)
    def failed(self,message):
        if 'prepared game file is missing or changed' in message and self.current:self.repair_games.add(self.current)
        self.message.setText(message);self.refresh()
        if getattr(self.worker,'title',None) in {'Check for updates','Download update'}:self.update_label.setText(message)
        if self.last_job and self.last_job.get('label') in {'Start Android container','Start Android'}:QMessageBox.warning(self,'Android startup failed',message)
        if 'Preparation tools are missing' in message:self.show_setup()
        elif 'java: not found' in message or 'Missing tool:' in message and 'java' in message:
            self.message.setText('Java could not start. Open Setup and choose Check / repair preparation tools, then retry Prepare.')
    def job_finished(self,owned=None):
        if owned is not None and self.worker is not owned:owned.deleteLater();return
        self.bar.hide();self.cancel_button.hide();self.add_button.setEnabled(True);self.demo_button.setEnabled(True);finished=self.worker;self.worker=None
        if finished:finished.deleteLater()
        self.update_details()
        if self.focus_play_after_prepare and self.play_button.isVisible() and self.play_button.isEnabled():self.play_button.setFocus()
        self.focus_play_after_prepare=False
        if self.closing:self.queued=None;QTimer.singleShot(0,self.close)
        elif self.queued:queued=self.queued;self.queued=None;self.submit(*queued)
        elif getattr(self,'pending_apks',[]):QTimer.singleShot(0,lambda:self.open_apk(self.pending_apks.pop(0)))
    def cancel(self):self.service.jobs.cancel();self.message.setText('Will cancel at the next safe stage. Finishing the current operation first.')
    def add_game(self,checked=False,apk=None):
        dialog=ImportDialog(apk,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        path=dialog.apk.text().strip()
        if not path:self.message.setText('Choose a base APK first.');return
        self.submit('Add game',lambda ctx:self.service.import_game(path,dialog.support,ctx),lambda p:(self.select(p['id']),self.refresh(),self.message.setText('Added '+p['title']+'. '+readiness(p)['detail'])))
    def open_apk(self,path):
        if self.worker and self.worker.isRunning():
            self.pending_apks=getattr(self,'pending_apks',[])+[path];return
        self.submit('Add APK',lambda ctx:self.service.import_game(path,[],ctx),lambda p:(self.select(p['id']),self.refresh(),self.message.setText('Added '+p['title']+'. Press Play.')))
    def demo(self):
        self.focus_play_after_prepare=True
        resource=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources/tapquest-original.apk'
        if not resource.exists():self.message.setText('Demo APK not bundled. Build the fixture or use the packaged download.');return
        def run(ctx):
            p=self.service.import_game(resource,[],ctx);return self.service.prepare(p['id'],'rebuild',ctx)
        self.submit('Prepare independent desktop demo',run,lambda p:(self.select(p['id']),self.refresh(),self.message.setText('Desktop demo prepared. It is a separate rebuild of the fixture. Select Play.')))
    def prepare(self):
        self.focus_play_after_prepare=True
        p=self.profile();game=p['id'];path=p.get('launcher',{}).get('preferred_path') or p['analysis']['recommended_path'];self.submit('Prepare '+p['title'],lambda ctx:self.service.prepare(game,path,ctx),lambda p:(self.repair_games.discard(game),self.refresh(),self.message.setText('Prepared successfully. Select Play to launch.')))
    def play(self):
        p=self.profile()
        # Play owns Android discovery/startup, saved APK deployment, and backend
        # startup. Do not force the user through Setup on each application restart.
        self.submit('Play '+p['title'],lambda ctx:self.service.play(p['id'],ctx),self.open_game)
    def run_library_request(self,value,reply):
        """Run local controls through the same worker/service as the buttons."""
        if self.worker or (self.monitor_worker and self.monitor_worker.isRunning()):return False
        action=value['action']
        if action=='quit':
            self.quit_request_reply=reply;QTimer.singleShot(0,self.close);return True
        callbacks={'play':self.open_game,'stop':lambda _:self.return_to_library()}
        if action=='play':
            game=value['game'];profile=self.service.store.load(game,check=False);self.select(game)
            title='Play '+profile['title']
        else:title={'stop':'Stop game','restart-runtime':'Restart Android'}[action]
        def run(ctx):
            try:
                if action=='play':
                    if self.service.active and self.service.active['game']==game:result=self.service.active
                    else:result=self.service.play(game,ctx)
                elif action=='stop':result=self.service.stop(ctx)
                else:
                    if self.service.active:raise RevivalError('Stop the running game before restarting its runtime.')
                    result=self.service.runtime_manager.restart_android(progress=ctx.step)
                reply(state='succeeded',job_id=ctx.job.id)
                return result
            except Exception as error:
                reply(state='failed',job_id=ctx.job.id,error=str(error));raise
        self.submit(title,run,callbacks.get(action));return True
    def open_game(self,session):
        self.game_started=True
        if session['kind']=='rebuild':
            self.rebuild_view=GameView(self.service.store.directory(session['game'])/'saves/rebuild.json',self.stop);self.stack.addWidget(self.rebuild_view);self.stack.setCurrentWidget(self.rebuild_view);self.active_page='game';self.activateWindow();QTimer.singleShot(10,self.rebuild_view.collect.setFocus)
        self.message.setText('Playing. Stop returns to your library.')
    def stop(self):self.submit('Stop game',lambda ctx:self.service.stop(ctx),lambda _:(self.return_to_library(),self.game_ended()))
    def game_ended(self):
        if self.close_after_game and self.game_started and not self.service.active:
            self.message.setText('Game ended. Returning to Steam...');QTimer.singleShot(1500,self.close)
    def return_to_library(self):
        self.stack.setCurrentWidget(self.library);self.active_page='library';self.set_page('library')
        if self.rebuild_view:self.stack.removeWidget(self.rebuild_view);self.rebuild_view.deleteLater();self.rebuild_view=None
        self.refresh()
    def back(self):
        if self.active_page=='game':self.stop()
        elif self.active_page!='library':self.return_to_library()
        elif self.isFullScreen():self.showNormal()
    def restart_android(self):
        if self.worker:return
        def restart(ctx):
            self.service.stop(ctx)
            self.service.runtime_manager.restart_android(progress=ctx.step)
            return self.service.runtime_manager.last
        self.submit('Restart Android',restart,self.runtime_result)
    def enable_runtime_access(self):
        if not self.service.runtime_manager.steam_bundle_launcher():
            self.message.setText('Password-free startup requires the existing SteamOS Waydroid main-profile installation.');return
        answer=QMessageBox.question(self,'Enable password-free runtime startup','Install a root-owned helper limited to the existing main Waydroid profile: image checks, mounting, container startup, shared storage and controller discovery? This requires one administrator authorization. It does not restart the running game, change your password, reset Android or grant password-free shell access.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        from .runtime_access import install
        self.submit('Runtime startup access',lambda ctx:install(ctx.step),lambda _:self.message.setText('Password-free runtime startup is configured. Your games and saves were not changed.'))
    def input_diagnostics(self):
        if self.worker:return
        from .input_diagnostics import collect,LABELS
        from PySide6.QtWidgets import QInputDialog
        choice,accepted=QInputDialog.getItem(self,'Input diagnostics','Choose a comparison. After capture begins, switch back to Android and repeat the same gestures for 10 seconds. This does not change settings.',LABELS,0,False)
        if not accepted:return
        self.submit('Input diagnostics',lambda ctx:collect(self.service,choice,ctx),lambda result:self.message.setText('Diagnostic report: '+result['directory']+(' — Android captured; this is not a latency measurement.' if result['android_captured'] else ' — Android was inaccessible; host evidence only.')))
    def show_setup(self):
        if self.active_page=='game':return
        self.stack.setCurrentWidget(self.setup);self.active_page='setup';self.set_page('setup');self.setup_scroll.verticalScrollBar().setValue(0);self.update_tools();self.check_runtime()
    def update_tools(self):
        h=tools_setup.health();missing=[n for n in ['java','keytool','zipalign','apksigner'] if not h[n]['ready']];self.tools_label.setText('Preparation tools found. Prepare checks their compatibility.' if not missing else 'Install the user-local tools needed to build and sign supported games.');self.install_tools_button.setText('Check / repair preparation tools' if not missing else 'Install preparation tools')
    def check_runtime(self):
        if self.worker:return
        self.submit('Check Android setup',lambda ctx:(ctx.step('Checking Android setup'),self.service.runtime_manager.discover())[1],self.runtime_result)
    def runtime_result(self,info):
        self.devices.blockSignals(True);self.devices.clear();self.devices.addItem('Choose an Android environment' if info['devices'] else 'No Android device connected yet',None)
        for device in info['devices']:
            self.devices.addItem(device['serial']+'  ('+device['state']+')',device['serial'] if device['state']=='device' else None)
        ready=[d for d in info['devices'] if d['state']=='device'];preferred=self.service.settings.get('serial')
        if len(ready)==1:preferred=ready[0]['serial'];self.service.settings['serial']=preferred;self.service.save_settings()
        index=self.devices.findData(preferred)
        if index>=0:self.devices.setCurrentIndex(index)
        self.devices.blockSignals(False)
        self.devices.setEnabled(bool(ready))
        self.runtime_label.setText('Android connected. Select the intended environment.' if ready else 'Waydroid is installed, but Android is not connected. Start Android or check its container.' if info['waydroid'] else 'Waydroid is not installed. Open the installation guide, then return and select Check again. The desktop demo works without Android.')
        if not ready and self.service.runtime_manager.steam_bundle_launcher():self.runtime_label.setText('SteamOS Waydroid bundle found. Open Library and press Play: APK Revival will start your preserved Android image and reconnect ADB automatically. A password prompt may appear.')
        self.connection_label.setText('Android: connected' if ready else 'Android: setup needed');self.connection_dot.setObjectName('dot_ok' if ready else 'dot_warn');restyle(self.connection_dot)
        if not ready and info.get('service')=='active' and not self.service.runtime_manager.steam_bundle_launcher():self.runtime_label.setText('Container service is running. Start Android to boot the user session, then Check again.')
        if not ready and info.get('session')=='RUNNING':self.runtime_label.setText('Android session is running, but ADB is not connected. '+('Guest IP: '+str(info['ip'])+'. Use Connect below. ' if info.get('ip') else '')+'Check the connection details below.')
        if not ready and any(d['state']=='unauthorized' for d in info['devices']):self.runtime_label.setText('Authorization needed. Choose Open Android and approve Allow USB debugging. Select Always allow from this computer, then Check again.')
        self.message.setText(self.service.runtime_manager.last_start_note or ('; '.join(info.get('errors',[])[-2:]) if not ready and info.get('errors') else 'Setup check complete.'));self.service.runtime_manager.last_start_note=None;self.update_details()
    def install_shortcut(self):
        if not getattr(sys,'frozen',False):
            self.message.setText('Desktop installation is available in the packaged Linux download.');return
        from .install import install_dialog
        install_dialog()
    def steam_help(self):
        from .steam import register
        result=register(pathlib.Path(sys.executable))
        QMessageBox.information(self,'Steam launcher','APK Revival is registered in Steam. Start Steam and select APK Revival in Gaming Mode.' if result['registered'] else result['reason'])

    def device_selected(self,index):
        self.service.settings['serial']=self.devices.itemData(index);self.service.save_settings()
    def show_updates(self):
        if self.active_page=='game':return
        self.stack.setCurrentWidget(self.setup);self.active_page='setup';self.set_page('updates');self.update_tools()
        target=next(b for b in self.setup.findChildren(QPushButton) if b.text()=='Check for updates');target.setFocus();self.setup_scroll.ensureWidgetVisible(target,16,24)
        self.message.setText('Check for updates, or install an official downloaded package here.')
    def updater_url(self):
        from .updater import RELEASES
        return RELEASES
    def github_access(self):
        token,ok=QInputDialog.getText(self,'Private GitHub releases','Optional read-only GitHub token with access to onlykappa/Apk-revival. Kept in memory until you close the app. Never included in diagnostics.',QLineEdit.EchoMode.Password)
        if ok:self.updater.token=token.strip() or None;self.update_label.setText('GitHub access set for this session.' if token.strip() else 'GitHub access cleared.')
    def check_updates(self):
        self.submit('Check for updates',lambda ctx:self.updater.check(ctx.step),self.update_checked)
    def update_checked(self,result):
        if not result['available']:self.update_label.setText('APK Revival '+result['version']+' is up to date.');return
        self.update_label.setText('APK Revival '+result['version']+' is available.')
        if self.service.active:self.message.setText('Stop the game before installing an update.');return
        answer=QMessageBox.question(self,'Update available','Download and install APK Revival '+result['version']+'? The app will restart. Games and saves stay in their separate data folder. The previous app is preserved.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:QTimer.singleShot(0,self.download_update)
    def download_update(self):
        if self.worker:QTimer.singleShot(100,self.download_update);return
        if not getattr(sys,'frozen',False):self.message.setText('Use the packaged Linux app to install updates.');return
        if self.service.active:self.message.setText('Stop the game before updating.');return
        self.submit('Download update',lambda ctx:self.updater.stage(ctx.step),self.update_staged)
    def install_downloaded_update(self):
        if self.service.active:self.message.setText('Stop the game before updating.');return
        if not getattr(sys,'frozen',False):self.message.setText('Use the packaged Linux app to install updates.');return
        path,_=QFileDialog.getOpenFileName(self,'Choose the official GitHub Linux update','','Linux update (*.tar.gz)')
        if not path:return
        answer=QMessageBox.question(self,'Install downloaded update','Install this package from the official APK Revival GitHub releases? Local packages must come from a source you trust. The app checks compatibility, installs it and restarts.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        from .updater import stage_archive
        self.submit('Stage downloaded update',lambda ctx:stage_archive(path,ctx.step),self.update_staged)
    def update_staged(self,result):
        self.pending_update=result;self.closing=True;self.message.setText('Update ready. Closing cleanly and restarting...');self.close()
    def install_tools(self):
        answer=QMessageBox.question(self,'Install preparation tools','Download Android SDK tools, apktool and Java when needed into your user cache? No administrator access is required. Upstream licenses apply. The operation needs internet access during setup.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:self.submit('Install preparation tools',lambda ctx:tools_setup.install(ctx.step),lambda _:self.update_tools())
    def open_android_ui(self):
        self.submit('Open Android',lambda ctx:(ctx.step('Opening the Android desktop'),self.service.runtime_manager.open_android_ui())[1],self.runtime_result)
    def start_android(self):
        def run(ctx):ctx.step('Starting your existing Android environment and connecting ADB');self.service.runtime_manager.ensure(self.service.settings.get('serial'));return self.service.runtime_manager.last
        self.submit('Start Android',run,self.runtime_result)
    def start_container(self):
        if self.service.runtime_manager.steam_bundle_launcher():
            answer=QMessageBox.question(self,'Start existing SteamOS Android','Start your existing SteamOS Waydroid image and reconnect Android? A Konsole password prompt may appear to mount the image. Your data is preserved; no Android reinitialization or package installation will occur.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if answer==QMessageBox.StandardButton.Yes:self.submit('Start existing Android',lambda ctx:(ctx.step('Starting the preserved SteamOS Waydroid image'),self.service.runtime_manager.start_container_authorized())[1],self.runtime_result)
            return
        answer=QMessageBox.question(self,'Start Waydroid container','This starts the existing waydroid-container.service using administrator authorization. On SteamOS, a Konsole password prompt may open. Enter your Deck administrator password there. This starts the service only; it does not install packages or change SteamOS protections. Continue?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:self.submit('Start Android container',lambda ctx:(ctx.step('Starting the existing Android container'),self.service.runtime_manager.start_container_authorized())[1],self.runtime_result)
    def installation_guide(self):QDesktopServices.openUrl(QUrl('https://docs.waydro.id/usage/install-on-desktops' if not self.service.runtime_manager.last.get('steam_os') else 'https://github.com/pjohno/steamos-waydroid-bundle'))
    def manual_connect(self):
        address=self.address.text();self.submit('Connect Android',lambda ctx:(ctx.step('Connecting the selected Android guest'),self.service.runtime_manager.connect_manual(address))[1],self.runtime_result)
    def options(self):
        if not self.current or (self.worker and self.worker.isRunning()):return
        p=self.profile();dialog=QDialog(self);dialog.setWindowTitle('Game options');dialog.resize(760,720);box,footer=dialog_shell(dialog,p['title'],'Saves, files and how this game is prepared.')
        def selected_file(title,save=False):
            return (QFileDialog.getSaveFileName(dialog,title,'APK-Revival-'+p['id'][:8]+'.zip','ZIP package (*.zip)') if save else QFileDialog.getOpenFileName(dialog,title,'','ZIP package (*.zip)'))[0]
        def start(title,fn):dialog.accept();self.submit(title,fn,lambda r:self.message.setText('Completed: '+(r.get('file','') if isinstance(r,dict) else str(r))))
        def export():
            output=selected_file('Export game package',True)
            if output:start('Export game',lambda ctx:self.service.export(p['id'],output,ctx))
        def diagnostics():
            output=selected_file('Export diagnostics',True)
            if output:start('Export diagnostics',lambda ctx:self.service.diagnostics(p['id'],output,ctx))
        def restore():
            folder=self.service.store.directory(p['id'])/'backups'
            backup=QFileDialog.getOpenFileName(dialog,'Restore a save backup',str(folder) if folder.is_dir() else '','ZIP package (*.zip)')[0]
            if backup:start('Restore save',lambda ctx:self.service.restore(p['id'],backup,ctx))
        def attach():
            picker=ImportDialog(str(self.service.store.base(p)),dialog);picker.apk.setReadOnly(True);picker.add.setText('Add supporting files')
            if picker.exec()==QDialog.DialogCode.Accepted and picker.support:start('Add supporting files',lambda ctx:self.service.attach(p['id'],picker.support,ctx))
        backups=self.service.backups(p['id'])
        latest=('Last backup: '+(friendly_date(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(backups[0].stat().st_mtime))) or 'saved')+'  ·  '+str(len(backups))+' kept') if backups else 'No backups yet.'
        box.addWidget(setting_card('folder','Saves','Back up your progress or restore an earlier backup. '+latest,button('Backup save',lambda:start('Backup save',lambda ctx:self.service.backup(p['id'],ctx))),button('Restore save',restore)))
        box.addWidget(setting_card('package','Game files','Add expansion files, or export a portable copy of this game.',button('Add supporting files',attach),button('Export game',export)))
        box.addWidget(setting_card('info','Troubleshooting','Share a privacy-safe report, or inspect the full evidence.',button('Export diagnostics',diagnostics),button('Advanced',lambda:(dialog.accept(),self.advanced()))))
        box.addWidget(setting_card('gamepad','Steam','Adds this game to Steam so it starts straight from Gaming Mode. Close Steam first.',button('Add game to Steam',lambda:(dialog.accept(),self.add_game_to_steam(p['id'])))))
        box.addWidget(setting_card('stop','Remove from library','Removes this game from APK Revival. Its saves and backups are kept.',button('Remove game',lambda:(dialog.accept(),self.remove_game(p['id'])))))
        if p.get('adapter')=='meego-1.32':
            box.addWidget(setting_card('refresh','New village','Starts with two Meego and no bonus supplies. Your previous island is backed up.',button('New village (no bonuses)',lambda:start('New village',lambda ctx:self.service.new_meego_village(p['id'],ctx)))))
        choice=QComboBox();choice.setMinimumWidth(240)
        for key,value in PATH_NAMES.items():choice.addItem(value,key)
        preferred=p.get('launcher',{}).get('preferred_path') or p['restoration']['path'] or (p['analysis']['recommended_path'] if p['analysis'] else 'offline_patch');choice.setCurrentIndex(choice.findData(preferred));choice.setEnabled(bool(p.get('adapter')));
        if p.get('adapter')=='meego-1.32':
            for i in range(choice.count()):choice.model().item(i).setEnabled(choice.itemData(i)=='local_backend')
        box.addWidget(setting_card('setup','Preparation method','A rebuild is a separate implementation. Prefer preserving the original APK when supported.',choice));box.addStretch()
        def save():
            current=self.service.store.load(p['id']);current.setdefault('launcher',{})['preferred_path']=choice.currentData();self.service.store.save(current);dialog.accept();self.update_details();self.message.setText('Preparation method saved. Prepare once if this method is new.')
        footer.addStretch();save_button=button('Save options',save,'primary');save_button.setMinimumWidth(130);footer.addWidget(save_button);close=button('Close',dialog.reject);close.setMinimumWidth(130);footer.addWidget(close);dialog.exec()
    def add_game_to_steam(self,game):
        p=self.service.store.load(game,check=False);icon=None;image=self.artwork(p)
        if image:
            icon=self.service.store.directory(game)/'artwork'/'steam-icon.png';icon.parent.mkdir(parents=True,exist_ok=True)
            if not image.save(str(icon),'PNG'):icon=None
        try:result=self.service.add_to_steam(game,icon)
        except RevivalError as error:QMessageBox.warning(self,'Add to Steam',str(error));return
        QMessageBox.information(self,'Add to Steam',(p['title']+' is already in Steam.' if result.get('already_present') else p['title']+' was added to Steam. Start Steam and find it under Non-Steam games.') if result['registered'] else result['reason'])
    def remove_game(self,game):
        p=self.service.store.load(game,check=False)
        box=QMessageBox(QMessageBox.Icon.Question,'Remove '+p['title'],'Remove '+p['title']+' from your library?\n\nIts saves and backups are kept in the removed-games folder.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,self)
        box.button(QMessageBox.StandardButton.Yes).setText('Remove');box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        uninstall=QCheckBox('Also uninstall it from Android. Its in-game progress is backed up first.');box.setCheckBox(uninstall)
        if box.exec()!=QMessageBox.StandardButton.Yes:return
        def done(result):
            self.art_cache.pop(game,None)
            if self.current==game:self.current=None
            self.refresh();self.message.setText('Removed '+result['title']+('. It was also uninstalled from Android' if result['uninstalled'] else '')+('. Saves kept in '+result['kept'] if result['kept'] else '.'))
        self.submit('Remove '+p['title'],lambda ctx:self.service.remove_game(game,uninstall.isChecked(),ctx),done)
    def advanced(self):
        p=self.profile();dialog=QDialog(self);dialog.resize(940,660);dialog.setWindowTitle('Advanced');box,footer=dialog_shell(dialog,'Advanced: '+p['title']);tabs=QTabWidget();box.addWidget(tabs,1)
        values=[('Evidence',markdown(p) if p['analysis'] else 'Not analyzed.'),('Profile',json.dumps(p,indent=2)),('Verification',json.dumps(p['verification'],indent=2)),('Activity',json.dumps(self.last_job or {},indent=2)),('Backend',json.dumps(p['restoration'].get('plan',{}).get('backend'),indent=2))]
        for title,text in values:w=QPlainTextEdit(text);w.setReadOnly(True);tabs.addTab(w,title)
        check=QCheckBox('Attempt offline gameplay verification after preparation');check.setChecked(self.service.settings.get('verify_after_prepare',True));check.toggled.connect(lambda value:(self.service.settings.update(verify_after_prepare=value),self.service.save_settings()));box.addWidget(check)
        footer.addWidget(button('Test offline now',lambda:(dialog.accept(),self.test_offline())));footer.addStretch();close=button('Close',dialog.accept);close.setMinimumWidth(130);footer.addWidget(close);dialog.exec()
    def test_offline(self):
        if self.profile().get('adapter')=='meego-1.32':
            from .meego_test import MeegoTestDialog
            dialog=MeegoTestDialog(self);self.meego_test_dialog=dialog
            try:dialog.exec()
            finally:self.meego_test_dialog=None
            self.refresh()
            if self.closing:QTimer.singleShot(0,self.close)
        else:self.submit('Verify offline',lambda ctx:self.service.verify(self.current,ctx),lambda result:self.message.setText('Verified Offline' if result['passed'] else 'Offline verification incomplete: '+result.get('error','Checks did not pass.')))
    def toggle_fullscreen(self):
        if self.isFullScreen():self.showNormal()
        else:self.showFullScreen()
        self.service.settings['fullscreen']=self.isFullScreen();self.service.save_settings()
    def changeEvent(self,event):
        if event.type()==QEvent.Type.WindowStateChange:
            text='Exit fullscreen' if self.isFullScreen() else 'Fullscreen';self.fullscreen_button.setText('' if self.compact else text);self.fullscreen_button.setToolTip(text if self.compact else '')
        super().changeEvent(event)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Resize and obj is getattr(self,'scroll',None) and self.cards:
            if max(1,(self.scroll.viewport().width()-4+TILE_GAP)//(TILE_WIDTH+TILE_GAP))!=self.columns:QTimer.singleShot(0,self.layout_cards)
        if event.type()==QEvent.Type.FocusIn and isinstance(obj,QWidget) and getattr(self,'setup_scroll',None) and self.setup_scroll.widget().isAncestorOf(obj):
            # Cards re-wrap as layout settles; scroll again once it has.
            self.setup_scroll.ensureWidgetVisible(obj,16,24);QTimer.singleShot(0,lambda target=obj:self.setup_scroll.ensureWidgetVisible(target,16,24) if target.hasFocus() else None)
        if event.type()==QEvent.Type.KeyPress and self.isActiveWindow():
            key=event.key();focus=QApplication.focusWidget()
            if key==Qt.Key.Key_F11:self.toggle_fullscreen();return True
            if key==Qt.Key.Key_Escape and not QApplication.activeModalWidget():self.back();return True
            if key in [Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Up,Qt.Key.Key_Down] and not isinstance(focus,(QLineEdit,QPlainTextEdit,QComboBox)):
                spatial_focus(self,{Qt.Key.Key_Left:'left',Qt.Key.Key_Right:'right',Qt.Key.Key_Up:'up',Qt.Key.Key_Down:'down'}[key]);return True
        return super().eventFilter(obj,event)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        if self.worker and self.worker.isRunning():self.message.setText('Wait for the current task before importing.');return
        files=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        apks=[p for p in files if pathlib.Path(p).suffix.lower() in ('.apk','.xapk','.apks','.apkm')]
        if not apks:self.message.setText('Unsupported file. Drop an .apk, .xapk, .apks or .apkm game file.');return
        self.open_apk(apks[0])
    def monitor(self):
        if not self.service.android or (self.worker and self.worker.isRunning()) or (self.monitor_worker and self.monitor_worker.isRunning()):return
        self.monitor_worker=Worker(self.service,'Check running game',lambda ctx:self.service.monitor(),self);self.monitor_worker.succeeded.connect(self.monitored);self.monitor_worker.finished.connect(self.monitor_finished);self.monitor_worker.start()
    def monitored(self,message):
        if not message:return
        self.message.setText(message)
        if not self.service.active:self.return_to_library();self.game_ended()
    def monitor_finished(self):
        if self.monitor_worker:self.monitor_worker.deleteLater();self.monitor_worker=None
        if self.closing:QTimer.singleShot(0,self.close)
        elif getattr(self,'pending_submission',None):
            pending=self.pending_submission;self.pending_submission=None
            QTimer.singleShot(0,lambda:self.submit(*pending))
        elif getattr(self,'pending_apks',[]):QTimer.singleShot(0,lambda:self.open_apk(self.pending_apks.pop(0)))
    def closeEvent(self,event):
        guided=getattr(self,"meego_test_dialog",None)
        if guided and not guided.test.finished:self.closing=True;event.ignore();guided.reject();return
        if (self.worker and self.worker.isRunning()) or (self.monitor_worker and self.monitor_worker.isRunning()):
            self.closing=True;self.service.jobs.cancel();self.message.setText('Finishing the current operation before closing. Cancelling at a safe stage.');event.ignore();return
        if self.service.android:
            self.closing=True;event.ignore();self.stop();return
        self.monitor_timer.stop();self.controller.close();QApplication.instance().removeEventFilter(self)
        try:self.service.shutdown()
        except Exception as e:
            print('Shutdown cleanup: '+str(e),file=sys.stderr)
            if getattr(self,'quit_request_reply',None):self.quit_request_reply(state='failed',error=str(e))
        else:
            if getattr(self,'quit_request_reply',None):self.quit_request_reply(state='succeeded')
        if self.pending_update:
            from .updater import restart_with_update
            try:restart_with_update(self.pending_update)
            except Exception as error:
                self.pending_update=None;self.closing=False;event.ignore();QMessageBox.critical(self,'Update failed',str(error));return
        event.accept()

def apply_font(app):
    from PySide6.QtGui import QFontDatabase
    available=set(QFontDatabase.families());font=QFont(app.font());font.setFamilies([f for f in FONT_FAMILIES if f in available] or [font.family()]);font.setPixelSize(14);app.setFont(font)

def run(store=None,fullscreen=False):
    app=QApplication.instance() or QApplication(sys.argv);app.setApplicationName('APK Revival');app.setStyle('Fusion');apply_font(app);app.setStyleSheet(STYLE);window=Window(store,fullscreen);window.show();return app.exec()


