from __future__ import annotations
import json,pathlib,sys,traceback
from PySide6.QtCore import QEvent,QPoint,QRect,Qt,QThread,QTimer,Signal
from PySide6.QtGui import QColor,QDesktopServices,QFont,QLinearGradient,QPainter,QPen,QPixmap,QIcon
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication,QAbstractButton,QCheckBox,QComboBox,QDialog,QFileDialog,QFrame,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QMainWindow,QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,QScrollArea,QStackedWidget,QTabWidget,QVBoxLayout,QWidget
from ..analysis import markdown
from ..backend import Progress
from ..store import Store
from ..util import RevivalError,now
from .controller import Controller,spatial_focus
from .presentation import CONTROL_PROFILES,readiness
from .service import Launcher
from .style import STYLE
from . import tools_setup

def brand_asset():
    return pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources/apk-revival-logo.png'

PATH_NAMES={'offline_patch':'Preserve the APK offline','local_backend':'Use a local backend','rebuild':'Create a separate rebuild'}

def label(text,kind=None,wrap=False):
    w=QLabel(text)
    if kind:w.setObjectName(kind)
    w.setWordWrap(wrap);return w

def button(text,action=None,kind=None):
    w=QPushButton(text)
    if kind:w.setObjectName(kind)
    if action:w.clicked.connect(action)
    return w

class Worker(QThread):
    update=Signal(object);succeeded=Signal(object);failed=Signal(str)
    def __init__(self,service,title,operation,parent=None):super().__init__(parent);self.service=service;self.title=title;self.operation=operation
    def run(self):
        try:self.succeeded.emit(self.service.jobs.run(self.title,self.operation,self.update.emit))
        except Exception as e:self.failed.emit(str(e))

class Poster(QWidget):
    def __init__(self,title='APK',seed='demo',parent=None):super().__init__(parent);self.title=title;self.seed=seed;self.setMinimumHeight(190)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palettes=[('#28645b','#162e38','#efce7d'),('#3d456f','#1a253f','#b5c8fa'),('#66475f','#281f3b','#e8b8d0')]
        a,b,accent=palettes[int(self.seed[:2],16)%3] if len(self.seed)>=2 and all(c in '0123456789abcdef' for c in self.seed[:2]) else palettes[0]
        gradient=QLinearGradient(0,0,self.width(),self.height());gradient.setColorAt(0,QColor(a));gradient.setColorAt(1,QColor(b));painter.setBrush(gradient);painter.setPen(Qt.PenStyle.NoPen);painter.drawRoundedRect(self.rect(),16,16)
        painter.setPen(QPen(QColor(255,255,255,32),2))
        for n in range(5):painter.drawEllipse(QPoint(int(self.width()*.78),int(self.height()*.45)),45+n*20,45+n*20)
        painter.setBrush(QColor(accent));painter.setPen(Qt.PenStyle.NoPen);painter.drawRoundedRect(QRect(int(self.width()*.68),38,58,95),13,13)
        painter.setPen(QPen(QColor(b),3));painter.drawLine(int(self.width()*.68)+17,108,int(self.width()*.68)+41,108)
        painter.setPen(QColor('#ffffff'));font=QFont('DejaVu Sans',25,QFont.Weight.Bold);painter.setFont(font)
        painter.drawText(QRect(20,20,int(self.width()*.62),self.height()-35),Qt.AlignmentFlag.AlignBottom|Qt.TextFlag.TextWordWrap,self.title)

class GameCard(QPushButton):
    def __init__(self,p,selected,action):
        super().__init__();self.setObjectName('card');self.setCheckable(True);self.setChecked(selected);self.setMinimumWidth(240);self.setFixedHeight(246);self.setMaximumWidth(350);self.setAccessibleName(p['title']);self.clicked.connect(action)
        box=QVBoxLayout(self);box.setContentsMargins(10,10,10,12);poster=Poster(p['title'],p['id']);poster.setMinimumHeight(160);poster.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);box.addWidget(poster)
        title=label(p['title']);title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);box.addWidget(title)
        detail=label('Independent rebuild' if p['restoration']['path']=='rebuild' else 'Android game','muted');detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);box.addWidget(detail)

class ImportDialog(QDialog):
    def __init__(self,apk=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Add game');self.resize(670,590);self.support=[]
        box=QVBoxLayout(self);box.setContentsMargins(28,24,28,24);box.addWidget(label('Add a mobile game','heading'));box.addWidget(label('Choose a base APK. Add supporting files if you have them.','muted',True))
        row=QHBoxLayout();self.apk=QLineEdit(apk or '');self.apk.setPlaceholderText('Select an APK');row.addWidget(self.apk);row.addWidget(button('Browse',self.pick_apk));box.addLayout(row)
        self.files=QPlainTextEdit();self.files.setReadOnly(True);self.files.setPlaceholderText('Optional matching OBBs, splits, assets, logs and saves');box.addWidget(self.files)
        actions=QGridLayout()
        actions.addWidget(button('OBBs / split APKs',lambda:self.pick_support(None)),0,0);actions.addWidget(button('Asset files',lambda:self.pick_support('asset')),0,1);actions.addWidget(button('Asset folder',self.pick_folder),1,0);actions.addWidget(button('Logs',lambda:self.pick_support('log')),1,1);actions.addWidget(button('Save files',lambda:self.pick_support('save')),2,0);box.addLayout(actions)
        box.addWidget(label('Originals stay unchanged. Private saves and logs are excluded from game exports.','muted',True));bottom=QHBoxLayout();bottom.addStretch();bottom.addWidget(button('Cancel',self.reject));self.add=button('Add game',self.accept,'primary');bottom.addWidget(self.add);box.addLayout(bottom)
    def pick_apk(self):
        file,_=QFileDialog.getOpenFileName(self,'Choose base APK','','Android APK (*.apk)')
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
        super().__init__();self.setObjectName('base');self.progress=Progress(save);box=QVBoxLayout(self);box.setContentsMargins(60,40,60,40)
        top=QHBoxLayout();top.addWidget(button('Back to library',back));top.addStretch();top.addWidget(label('INDEPENDENT DESKTOP REBUILD','tag'));box.addLayout(top);box.addStretch();box.addWidget(label('Tap Quest','heading'),alignment=Qt.AlignmentFlag.AlignCenter)
        self.state=label('','readiness');box.addWidget(self.state,alignment=Qt.AlignmentFlag.AlignCenter);self.collect=button('Collect coin',self.action,'play');self.collect.setMinimumWidth(380);box.addWidget(self.collect,alignment=Qt.AlignmentFlag.AlignCenter)
        box.addWidget(label('Every 10 coins raises your level. Progress saves after every action.','muted'),alignment=Qt.AlignmentFlag.AlignCenter);box.addStretch();self.refresh();self.collect.setFocus()
    def refresh(self):
        state=self.progress.get();self.state.setText(f'Coins: {state["coins"]}     Level: {state["level"]}')
    def action(self):self.progress.collect();self.refresh()

class Window(QMainWindow):
    def __init__(self,store=None,fullscreen=False):
        super().__init__();self.service=Launcher(store or Store());self.current=None;self.worker=None;self.monitor_worker=None;self.cards=[];self.last_job=None;self.rebuild_view=None;self.active_page='library';self.closing=False
        self.setWindowTitle('APK Revival');self.setWindowIcon(QIcon(str(brand_asset())));self.resize(1280,800);self.setMinimumSize(1000,650);self.setAcceptDrops(True)
        root=QWidget();root.setObjectName('base');self.setCentralWidget(root);outer=QVBoxLayout(root);outer.setContentsMargins(28,20,28,18);outer.setSpacing(16)
        header=QHBoxLayout();mark=QLabel();mark.setPixmap(QPixmap(str(brand_asset())).scaled(58,58,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));mark.setFixedSize(58,58);header.addWidget(mark);brand=QVBoxLayout();brand.setSpacing(1);brand.addWidget(label('APK REVIVAL','brand'));brand.addWidget(label('Mobile games. Back in play.','muted'));header.addLayout(brand);header.addStretch();from .. import __version__;header.addWidget(label('V'+__version__,'tag'))
        self.setup_button=button('Setup',self.show_setup);header.addWidget(self.setup_button);header.addWidget(button('Fullscreen',self.toggle_fullscreen,'quiet'));self.add_button=button('+ Add game',self.add_game,'primary');header.addWidget(self.add_button);outer.addLayout(header)
        self.stack=QStackedWidget();outer.addWidget(self.stack,1);self.library=self.library_page();self.stack.addWidget(self.library);self.setup=self.setup_page();self.stack.addWidget(self.setup)
        self.feedback=QFrame();self.feedback.setObjectName('panel');feedback=QHBoxLayout(self.feedback);feedback.setContentsMargins(18,10,18,10);self.message=label('Ready. Add a game or try the included desktop demo.','muted',True);feedback.addWidget(self.message,1);self.cancel_button=button('Cancel task',self.cancel,'quiet');feedback.addWidget(self.cancel_button);self.cancel_button.hide();outer.addWidget(self.feedback)
        self.bar=QProgressBar();self.bar.setRange(0,0);self.bar.hide();outer.addWidget(self.bar)
        footer=QHBoxLayout();footer.addWidget(label('A / Enter  Select     B / Esc  Back     D-pad / Arrows  Navigate','muted'));footer.addStretch();self.connection_label=label('Android: not checked','muted');footer.addWidget(self.connection_label);outer.addLayout(footer)
        self.controller=Controller(self,self.back,self.options);QApplication.instance().installEventFilter(self);self.refresh()
        self.monitor_timer=QTimer(self);self.monitor_timer.timeout.connect(self.monitor);self.monitor_timer.start(5000)
        if fullscreen or self.service.settings.get('fullscreen'):self.showFullScreen()
        QTimer.singleShot(80,self.check_runtime)
    def library_page(self):
        page=QWidget();layout=QHBoxLayout(page);layout.setContentsMargins(0,0,0,0);layout.setSpacing(24)
        left=QWidget();left_box=QVBoxLayout(left);left_box.setContentsMargins(0,0,0,0);head=QHBoxLayout();head.addWidget(label('Library','heading'));head.addStretch();self.demo_button=button('Try desktop demo',self.demo,'quiet');head.addWidget(self.demo_button);left_box.addLayout(head)
        self.search=QLineEdit();self.search.setPlaceholderText('Search your games');self.search.textChanged.connect(self.refresh);left_box.addWidget(self.search)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.grid_host=QWidget();self.grid_host.setObjectName('grid_host');self.grid=QGridLayout(self.grid_host);self.grid.setContentsMargins(0,5,3,0);self.grid.setSpacing(16);self.grid.setAlignment(Qt.AlignmentFlag.AlignTop);self.scroll.setWidget(self.grid_host);left_box.addWidget(self.scroll,1);layout.addWidget(left,3)
        self.details=QFrame();self.details.setObjectName('panel');self.details.setMinimumWidth(390);self.details.setMaximumWidth(480);right=QVBoxLayout(self.details);right.setContentsMargins(24,20,24,20);right.setSpacing(9)
        self.hero=Poster('ADD A GAME','demo');self.hero.setFixedHeight(132);right.addWidget(self.hero);self.game_title=label('Your next revival','heading');self.game_title.setStyleSheet('font-size: 26px; font-weight: 700');right.addWidget(self.game_title);self.game_kind=label('LOCAL LIBRARY','tag');right.addWidget(self.game_kind)
        self.readiness_label=label('Start with an APK','readiness',True);right.addWidget(self.readiness_label);self.description=label('Choose a game file. APK Revival checks what it needs and keeps the original untouched.','muted',True);right.addWidget(self.description)
        self.play_button=button('Play',self.play,'play');self.play_button.setMinimumHeight(48);right.addWidget(self.play_button);actions=QHBoxLayout();self.prepare_button=button('Prepare',self.prepare);actions.addWidget(self.prepare_button);self.stop_button=button('Stop',self.stop);actions.addWidget(self.stop_button);self.options_button=button('Game options',self.options,'quiet');actions.addWidget(self.options_button);right.addLayout(actions);right.addStretch();self.controls_label=label('Touch, trackpad and controller-aware browsing.','muted',True);right.addWidget(self.controls_label);layout.addWidget(self.details,2);return page
    def setup_page(self):
        page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(8,0,8,10);row=QHBoxLayout();row.addWidget(button('Back',self.back));row.addStretch();box.addLayout(row);box.addWidget(label('Make it ready to play','heading'));box.addWidget(label('Preparation tools and the Android environment are managed separately.','muted'))
        tools_panel=QFrame();tools_panel.setObjectName('panel');tb=QVBoxLayout(tools_panel);tb.setContentsMargins(24,20,24,20);tb.addWidget(label('1   Preparation tools','readiness'));self.tools_label=label('Checking tools...','muted',True);tb.addWidget(self.tools_label);self.install_tools_button=button('Install preparation tools',self.install_tools,'primary');tb.addWidget(self.install_tools_button);box.addWidget(tools_panel)
        android_panel=QFrame();android_panel.setObjectName('panel');ab=QVBoxLayout(android_panel);ab.setContentsMargins(24,20,24,20);ab.addWidget(label('2   Android environment','readiness'));self.runtime_label=label('Check for an existing Waydroid installation.','muted',True);ab.addWidget(self.runtime_label);self.devices=QComboBox();self.devices.setAccessibleName('Android device');self.devices.currentIndexChanged.connect(self.device_selected);ab.addWidget(self.devices)
        controls=QHBoxLayout();controls.addWidget(button('Check again',self.check_runtime));controls.addWidget(button('Start Android',self.start_android));controls.addWidget(button('Start container',self.start_container));controls.addWidget(button('Installation guide',self.installation_guide,'quiet'));ab.addLayout(controls)
        manual=QHBoxLayout();self.address=QLineEdit();self.address.setPlaceholderText('Optional: Android guest IP');manual.addWidget(self.address);manual.addWidget(button('Connect',self.manual_connect));ab.addLayout(manual);box.addWidget(android_panel)
        install_row=QHBoxLayout();install_row.addWidget(button('Install desktop shortcut',self.install_shortcut));install_row.addWidget(button('Add to Steam',self.steam_help,'quiet'));install_row.addStretch();box.addLayout(install_row);box.addStretch();box.addWidget(label('SteamOS needs a compatible kernel and Wayland setup. Host installation is guided; system protections are not changed automatically.','muted',True));return page
    def refresh(self,*_):
        old_focus=QApplication.focusWidget();focus_game=old_focus.property('game_id') if old_focus else None
        self.cards=[]
        while self.grid.count():
            item=self.grid.takeAt(0)
            widget=item.widget()
            if widget:widget.hide();widget.setParent(None);widget.deleteLater()
        games=self.service.store.games();query=self.search.text().casefold();filtered=[p for p in games if query in p['title'].casefold()]
        if not self.current and games:self.current=games[0]['id']
        for index,p in enumerate(filtered):
            card=GameCard(p,p['id']==self.current,lambda checked=False,game=p['id']:self.select(game));card.setProperty('game_id',p['id']);self.grid.addWidget(card,index//2,index%2);self.cards.append(card)
            if p['id']==focus_game:card.setFocus()
        if not filtered:
            if games:self.grid.addWidget(label('No matches.','muted'),0,0,1,2)
            else:
                welcome=QFrame();welcome.setObjectName('welcome');welcome.setMinimumHeight(360);box=QVBoxLayout(welcome);box.setContentsMargins(28,28,28,28);box.addStretch();mark=QLabel();mark.setPixmap(QPixmap(str(brand_asset())).scaled(110,110,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));box.addWidget(mark,alignment=Qt.AlignmentFlag.AlignCenter);box.addWidget(label('Bring your games back.','heading'),alignment=Qt.AlignmentFlag.AlignCenter);copy=label('Drop an APK here to start your library.\nOr try Tap Quest, included and ready to explore.','muted',True);copy.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(copy);box.addStretch();self.grid.addWidget(welcome,0,0,1,2)
        self.update_details();self.update_tools()
    def select(self,game):
        self.current=game
        for c in self.cards:c.setChecked(c.property('game_id')==game)
        self.update_details()
    def profile(self):
        if not self.current:raise RevivalError('Add or select a game first.')
        return self.service.store.load(self.current,check=False)
    def update_details(self):
        if not self.current:
            for w in [self.play_button,self.prepare_button,self.stop_button,self.options_button]:w.setEnabled(False)
            return
        p=self.profile();ready=readiness(p,self.service.runtime_manager.last.get('ready',False));self.game_title.setText(p['title'] if len(p['title'])<26 else p['title'][:24]+'...');self.game_title.setToolTip(p['title']);self.hero.title=p['title'];self.hero.seed=p['id'];self.hero.update();self.game_kind.setText('INDEPENDENT REBUILD' if p['restoration']['path']=='rebuild' else 'ANDROID GAME'+('  /  SELF-AUTHORED FIXTURE' if p['analysis'] and p['analysis']['fixture'] else ''));self.readiness_label.setText(ready['label']);self.description.setText(ready['detail'])
        busy=bool(self.worker and self.worker.isRunning());active=self.service.active
        self.play_button.setEnabled(bool(not busy and not active and (ready['play'] or (p['restoration'].get('artifact') and ready['label']=='Runtime setup needed'))));self.play_button.setText('Set up Android' if ready['label']=='Runtime setup needed' else 'Play');self.prepare_button.setEnabled(not busy and not active and ready['prepare']);self.stop_button.setEnabled(not busy and bool(active));self.options_button.setEnabled(not busy)
        control=CONTROL_PROFILES.get(p.get('adapter'),{'description':'Controls are unknown until this game is investigated.'});self.controls_label.setText('Controls: A / Enter collects. B / Esc returns.' if p['restoration']['path']=='rebuild' else 'Controls: touch or trackpad.' if p.get('adapter') in {'tapquest-v1','meego-1.32'} else 'Controls need game-specific investigation.')
    def submit(self,title,operation,callback=None):
        if self.worker:return
        self.worker=Worker(self.service,title,operation,self);worker=self.worker;self.callback=callback;worker.update.connect(self.progress);worker.succeeded.connect(self.completed);worker.failed.connect(self.failed);worker.finished.connect(lambda owned=worker:self.job_finished(owned));self.bar.show();self.cancel_button.show();self.add_button.setEnabled(False);self.demo_button.setEnabled(False);worker.start();self.update_details()
    def progress(self,job):
        self.last_job=job;step=job['steps'][-1]['label'] if job['steps'] else job['label'];self.message.setText(step+('...' if job['state']=='running' else ''))
    def completed(self,result):
        self.message.setText('Completed.');self.refresh()
        if self.active_page=='game' and not self.service.active:self.return_to_library()
        if self.callback:self.callback(result)
    def failed(self,message):
        self.message.setText(message);self.refresh()
        if 'Preparation tools are missing' in message:self.show_setup()
    def job_finished(self,owned=None):
        if owned is not None and self.worker is not owned:owned.deleteLater();return
        self.bar.hide();self.cancel_button.hide();self.add_button.setEnabled(True);self.demo_button.setEnabled(True);self.update_details();self.worker.deleteLater();self.worker=None
        if self.closing:QTimer.singleShot(0,self.close)
    def cancel(self):self.service.jobs.cancel();self.message.setText('Will cancel at the next safe stage. Finishing the current operation first.')
    def add_game(self,checked=False,apk=None):
        dialog=ImportDialog(apk,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        path=dialog.apk.text().strip()
        if not path:self.message.setText('Choose a base APK first.');return
        self.submit('Add game',lambda ctx:self.service.import_game(path,dialog.support,ctx),lambda p:(self.select(p['id']),self.refresh(),self.message.setText('Added '+p['title']+'. '+readiness(p)['detail'])))
    def demo(self):
        resource=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources/tapquest-original.apk'
        if not resource.exists():self.message.setText('Demo APK not bundled. Build the fixture or use the packaged download.');return
        def run(ctx):
            p=self.service.import_game(resource,[],ctx);return self.service.prepare(p['id'],'rebuild',ctx)
        self.submit('Prepare independent desktop demo',run,lambda p:(self.select(p['id']),self.refresh(),self.message.setText('Desktop demo prepared. It is a separate rebuild of the fixture. Select Play.')))
    def prepare(self):
        p=self.profile();game=p['id'];path=p.get('launcher',{}).get('preferred_path') or p['analysis']['recommended_path'];self.submit('Prepare '+p['title'],lambda ctx:self.service.prepare(game,path,ctx),lambda p:self.message.setText('Prepared. '+readiness(p,self.service.runtime_manager.last.get('ready',False))['detail']))
    def play(self):
        p=self.profile()
        if readiness(p,self.service.runtime_manager.last.get('ready',False))['label']=='Runtime setup needed':self.show_setup();return
        self.submit('Play '+p['title'],lambda ctx:self.service.play(p['id'],ctx),self.open_game)
    def open_game(self,session):
        if session['kind']=='rebuild':
            self.rebuild_view=GameView(self.service.store.directory(session['game'])/'saves/rebuild.json',self.stop);self.stack.addWidget(self.rebuild_view);self.stack.setCurrentWidget(self.rebuild_view);self.active_page='game';self.activateWindow();QTimer.singleShot(10,self.rebuild_view.collect.setFocus)
        self.message.setText('Playing. Stop returns to your library.' if session['kind']=='rebuild' else 'Android activity launched. Offline gameplay remains subject to verification.')
    def stop(self):self.submit('Stop game',lambda ctx:self.service.stop(ctx),lambda _:self.return_to_library())
    def return_to_library(self):
        self.stack.setCurrentWidget(self.library);self.active_page='library'
        if self.rebuild_view:self.stack.removeWidget(self.rebuild_view);self.rebuild_view.deleteLater();self.rebuild_view=None
        self.refresh()
    def back(self):
        if self.active_page=='game':self.stop()
        elif self.active_page!='library':self.return_to_library()
        elif self.isFullScreen():self.showNormal()
    def show_setup(self):self.stack.setCurrentWidget(self.setup);self.active_page='setup';self.update_tools();self.check_runtime()
    def update_tools(self):
        h=tools_setup.health();missing=[n for n in ['java','keytool','zipalign','apksigner'] if not h[n]['ready']];self.tools_label.setText('Preparation tools found. Prepare checks their compatibility.' if not missing else 'Install the user-local tools needed to build and sign supported games.');self.install_tools_button.setText('Check / repair preparation tools' if not missing else 'Install preparation tools')
    def check_runtime(self):
        if self.worker:return
        self.submit('Check Android setup',lambda ctx:(ctx.step('Checking Android setup'),self.service.runtime_manager.discover())[1],self.runtime_result)
    def runtime_result(self,info):
        self.devices.blockSignals(True);self.devices.clear();self.devices.addItem('Choose an Android environment',None)
        for device in info['devices']:
            self.devices.addItem(device['serial']+'  ('+device['state']+')',device['serial'] if device['state']=='device' else None)
        ready=[d for d in info['devices'] if d['state']=='device'];preferred=self.service.settings.get('serial')
        if len(ready)==1:preferred=ready[0]['serial'];self.service.settings['serial']=preferred;self.service.save_settings()
        index=self.devices.findData(preferred)
        if index>=0:self.devices.setCurrentIndex(index)
        self.devices.blockSignals(False)
        self.runtime_label.setText('Android connected. Select the intended environment.' if ready else 'Waydroid is installed, but Android is not connected. Start Android or check its container.' if info['waydroid'] else 'Waydroid is not installed. Open the installation guide, then return and select Check again. The desktop demo works without Android.')
        self.connection_label.setText('Android: connected' if ready else 'Android: setup needed');self.message.setText('Setup check complete.');self.update_details()
    def install_shortcut(self):
        if not getattr(sys,'frozen',False):
            self.message.setText('Desktop installation is available in the packaged Linux download.');return
        from .install import install_dialog
        install_dialog()
    def steam_help(self):
        path=pathlib.Path.home()/'.local/share/apk-revival-app/APK-Revival'
        QMessageBox.information(self,'Add APK Revival to Steam','Install the desktop shortcut first. Then open Steam in Desktop Mode and choose Games > Add a Non-Steam Game. Select APK Revival, or browse to:\n\n'+str(path)+'\n\nLaunch the shortcut from Gaming Mode. Its desktop entry enables fullscreen automatically.')
    def device_selected(self,index):
        self.service.settings['serial']=self.devices.itemData(index);self.service.save_settings()
    def install_tools(self):
        answer=QMessageBox.question(self,'Install preparation tools','Download Android SDK tools, apktool and Java when needed into your user cache? No administrator access is required. Upstream licenses apply. The operation needs internet access during setup.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:self.submit('Install preparation tools',lambda ctx:tools_setup.install(ctx.step),lambda _:self.update_tools())
    def start_android(self):
        def run(ctx):ctx.step('Starting the Android session');self.service.runtime_manager.ensure(self.service.settings.get('serial'));return self.service.runtime_manager.last
        self.submit('Start Android',run,self.runtime_result)
    def start_container(self):
        answer=QMessageBox.question(self,'Start Waydroid container','This starts the existing waydroid-container.service using administrator authorization. It does not install packages or change SteamOS protections. Continue?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:self.submit('Start Android container',lambda ctx:(ctx.step('Starting the existing Android container'),self.service.runtime_manager.start_container_authorized())[1],self.runtime_result)
    def installation_guide(self):QDesktopServices.openUrl(QUrl('https://docs.waydro.id/usage/install-on-desktops' if not self.service.runtime_manager.last.get('steam_os') else 'https://github.com/pjohno/steamos-waydroid-bundle'))
    def manual_connect(self):
        address=self.address.text();self.submit('Connect Android',lambda ctx:(ctx.step('Connecting the selected Android guest'),self.service.runtime_manager.connect_manual(address))[1],self.runtime_result)
    def options(self):
        if not self.current or (self.worker and self.worker.isRunning()):return
        p=self.profile();dialog=QDialog(self);dialog.setWindowTitle('Game options');dialog.resize(720,620);box=QVBoxLayout(dialog);box.setContentsMargins(26,22,26,22);box.addWidget(label(p['title'],'heading'));box.addWidget(label('Saves, supporting files, and advanced restoration settings.','muted',True))
        actions=QGridLayout();box.addLayout(actions)
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
            backup=selected_file('Restore matching save backup')
            if backup:start('Restore save',lambda ctx:self.service.restore(p['id'],backup,ctx))
        def attach():
            picker=ImportDialog(str(self.service.store.base(p)),dialog);picker.apk.setReadOnly(True);picker.add.setText('Add supporting files')
            if picker.exec()==QDialog.DialogCode.Accepted and picker.support:start('Add supporting files',lambda ctx:self.service.attach(p['id'],picker.support,ctx))
        actions.addWidget(button('Backup save',lambda:start('Backup save',lambda ctx:self.service.backup(p['id'],ctx))),0,0);actions.addWidget(button('Restore save',restore),0,1);actions.addWidget(button('Add supporting files',attach),1,0);actions.addWidget(button('Export game',export),1,1);actions.addWidget(button('Export diagnostics',diagnostics),2,0);actions.addWidget(button('Advanced',lambda:(dialog.accept(),self.advanced())),2,1)
        box.addWidget(label('Preparation path','muted'));choice=QComboBox()
        for key,value in PATH_NAMES.items():choice.addItem(value,key)
        preferred=p.get('launcher',{}).get('preferred_path') or p['restoration']['path'] or (p['analysis']['recommended_path'] if p['analysis'] else 'offline_patch');choice.setCurrentIndex(choice.findData(preferred));choice.setEnabled(bool(p.get('adapter')));
        if p.get('adapter')=='meego-1.32':
            for i in range(choice.count()):choice.model().item(i).setEnabled(choice.itemData(i)=='local_backend')
        box.addWidget(choice)
        box.addWidget(label('A rebuild is a separate implementation. Prefer preserving the original APK when supported.','muted',True));box.addStretch()
        def save():
            current=self.service.store.load(p['id']);current.setdefault('launcher',{})['preferred_path']=choice.currentData();self.service.store.save(current);dialog.accept();self.message.setText('Path selected. Prepare applies it to a separate working copy.')
        bottom=QHBoxLayout();bottom.addWidget(button('Close',dialog.reject));bottom.addStretch();bottom.addWidget(button('Save options',save,'primary'));box.addLayout(bottom);dialog.exec()
    def advanced(self):
        p=self.profile();dialog=QDialog(self);dialog.resize(940,650);dialog.setWindowTitle('Advanced');box=QVBoxLayout(dialog);box.addWidget(label('Advanced: '+p['title'],'heading'));tabs=QTabWidget();box.addWidget(tabs,1)
        values=[('Evidence',markdown(p) if p['analysis'] else 'Not analyzed.'),('Profile',json.dumps(p,indent=2)),('Verification',json.dumps(p['verification'],indent=2)),('Activity',json.dumps(self.last_job or {},indent=2)),('Backend',json.dumps(p['restoration'].get('plan',{}).get('backend'),indent=2))]
        for title,text in values:w=QPlainTextEdit(text);w.setReadOnly(True);tabs.addTab(w,title)
        check=QCheckBox('Attempt offline gameplay verification after preparation');check.setChecked(self.service.settings.get('verify_after_prepare',True));check.toggled.connect(lambda value:(self.service.settings.update(verify_after_prepare=value),self.service.save_settings()));box.addWidget(check)
        bottom=QHBoxLayout();bottom.addWidget(button('Test offline now',lambda:(dialog.accept(),self.test_offline())));bottom.addStretch();bottom.addWidget(button('Close',dialog.accept));box.addLayout(bottom);dialog.exec()
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
    def eventFilter(self,obj,event):
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
        apks=[p for p in files if pathlib.Path(p).suffix.lower()=='.apk']
        if not apks:self.message.setText('Unsupported input. Drop a base APK. XAPK/APKS containers must be unpacked first.');return
        self.add_game(apk=apks[0])
    def monitor(self):
        if not self.service.android or (self.worker and self.worker.isRunning()) or (self.monitor_worker and self.monitor_worker.isRunning()):return
        self.monitor_worker=Worker(self.service,'Check running game',lambda ctx:self.service.monitor(),self);self.monitor_worker.succeeded.connect(lambda message:(self.message.setText(message),self.return_to_library()) if message else None);self.monitor_worker.finished.connect(self.monitor_finished);self.monitor_worker.start()
    def monitor_finished(self):
        if self.monitor_worker:self.monitor_worker.deleteLater();self.monitor_worker=None
        if self.closing:QTimer.singleShot(0,self.close)
    def closeEvent(self,event):
        guided=getattr(self,"meego_test_dialog",None)
        if guided and not guided.test.finished:self.closing=True;event.ignore();guided.reject();return
        if (self.worker and self.worker.isRunning()) or (self.monitor_worker and self.monitor_worker.isRunning()):
            self.closing=True;self.service.jobs.cancel();self.message.setText('Finishing the current operation before closing. Cancelling at a safe stage.');event.ignore();return
        if self.service.android:
            self.closing=True;event.ignore();self.stop();return
        self.monitor_timer.stop();self.controller.close();QApplication.instance().removeEventFilter(self)
        try:self.service.shutdown()
        except Exception as e:print('Shutdown cleanup: '+str(e),file=sys.stderr)
        event.accept()

def run(store=None,fullscreen=False):
    app=QApplication.instance() or QApplication(sys.argv);app.setApplicationName('APK Revival');app.setStyle('Fusion');app.setStyleSheet(STYLE);window=Window(store,fullscreen);window.show();return app.exec()
