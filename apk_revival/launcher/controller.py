"""SDL2 controller polling and spatial focus, ported from OmniPC UI patterns.

OmniPC source: src/renderer/lib/gamepad.ts and spatial.ts (MIT).
See resources/OMNIPC-LICENSE.txt for attribution.
"""
from __future__ import annotations
import ctypes,ctypes.util,pathlib,sys,time
from PySide6.QtCore import QPoint,QTimer,Qt
from PySide6.QtWidgets import QApplication,QAbstractButton,QComboBox,QLineEdit,QScrollArea,QWidget

BUTTONS={0:'confirm',1:'back',3:'options',6:'menu',11:'up',12:'down',13:'left',14:'right'}
GAME_BUTTONS=(0,1,2,3,4,6,7,8,9,10,11,12,13,14)  # Forwarded to game_buttons while a game has focus.

def spatial_focus(window,direction):
    scope=QApplication.activeModalWidget() or window
    widgets=[w for w in scope.findChildren(QWidget) if isinstance(w,(QAbstractButton,QComboBox,QLineEdit)) and w.isVisible() and w.isEnabled() and w.focusPolicy()!=Qt.FocusPolicy.NoFocus]
    if not widgets:return
    current=QApplication.focusWidget()
    if current not in widgets:widgets[0].setFocus();return
    origin=current.mapTo(scope,QPoint(0,0));ax=origin.x()+current.width()/2;ay=origin.y()+current.height()/2;best=None;score=float('inf')
    for w in widgets:
        if w is current:continue
        p=w.mapTo(scope,QPoint(0,0));dx=p.x()+w.width()/2-ax;dy=p.y()+w.height()/2-ay
        if direction=='up':
            if p.y()+w.height()>origin.y()+4:continue
            primary=-dy;secondary=abs(dx)
        elif direction=='down':
            if p.y()<origin.y()+current.height()-4:continue
            primary=dy;secondary=abs(dx)
        elif direction=='left':
            if p.x()+w.width()>origin.x()+4:continue
            primary=-dx;secondary=abs(dy)
        else:
            if p.x()<origin.x()+current.width()-4:continue
            primary=dx;secondary=abs(dy)
        value=primary+secondary*2.2
        if value<score:score=value;best=w
    if best:
        best.setFocus();parent=best.parentWidget()
        while parent:
            if isinstance(parent,QScrollArea):parent.ensureWidgetVisible(best,24,24);break
            parent=parent.parentWidget()

def choose_in_dropdown(combo,action):
    view=combo.view();model=combo.model();row=view.currentIndex().row()
    if row<0:row=combo.currentIndex()
    if action in {'up','down'}:
        step=-1 if action=='up' else 1;candidate=row+step
        while 0<=candidate<combo.count() and not (model.flags(model.index(candidate,0))&Qt.ItemFlag.ItemIsEnabled):candidate+=step
        if 0<=candidate<combo.count():view.setCurrentIndex(model.index(candidate,0))
    elif action=='confirm':
        if row>=0:combo.setCurrentIndex(row)
        combo.hidePopup()
    elif action=='back':combo.hidePopup()

class Controller:
    def __init__(self,window,back,options):
        self.window=window;self.back=back;self.options=options;self.lib=None;self.handles={};self.previous={};self.last_dir=None;self.repeat=0;self.connected=[];self.error=None;self.game_buttons=None
        try:
            frozen=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).parent))/'libSDL2-2.0.so.0'
            location=str(frozen) if frozen.is_file() else ctypes.util.find_library('SDL2-2.0')
            if not location:raise OSError('SDL2 unavailable')
            lib=ctypes.CDLL(location);self.lib=lib
            for name,args,result in [('SDL_InitSubSystem',[ctypes.c_uint32],ctypes.c_int),('SDL_NumJoysticks',[],ctypes.c_int),('SDL_IsGameController',[ctypes.c_int],ctypes.c_int),('SDL_GameControllerOpen',[ctypes.c_int],ctypes.c_void_p),('SDL_GameControllerGetAttached',[ctypes.c_void_p],ctypes.c_int),('SDL_GameControllerClose',[ctypes.c_void_p],None),('SDL_GameControllerGetButton',[ctypes.c_void_p,ctypes.c_int],ctypes.c_uint8),('SDL_GameControllerGetAxis',[ctypes.c_void_p,ctypes.c_int],ctypes.c_int16),('SDL_GameControllerName',[ctypes.c_void_p],ctypes.c_char_p),('SDL_GameControllerUpdate',[],None),('SDL_QuitSubSystem',[ctypes.c_uint32],None)]:
                f=getattr(lib,name);f.argtypes=args;f.restype=result
            try:lib.SDL_JoystickGetDeviceInstanceID.argtypes=[ctypes.c_int];lib.SDL_JoystickGetDeviceInstanceID.restype=ctypes.c_int32
            except AttributeError:pass  # Very old SDL: fall back to device indexes.
            try:lib.SDL_SetHint.argtypes=[ctypes.c_char_p,ctypes.c_char_p];lib.SDL_SetHint(b'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS',b'1')
            except AttributeError:pass
            if lib.SDL_InitSubSystem(0x2000|0x200)!=0:raise OSError('Controller subsystem unavailable')
        except OSError as e:self.error=str(e);self.lib=None
        self.timer=QTimer(window);self.timer.timeout.connect(self.poll);self.timer.start(40)
    def dispatch(self,action):
        popup=QApplication.activePopupWidget()
        if popup:
            # An open dropdown takes the controller, not spatial focus or window actions.
            combo=popup.parentWidget() if isinstance(popup.parentWidget(),QComboBox) else None
            if combo:choose_in_dropdown(combo,action)
            elif action=='back':popup.close()
            return
        active=QApplication.activeModalWidget() or self.window
        if not active.isActiveWindow():return
        if action in {'up','down','left','right'}:spatial_focus(active,action)
        elif action=='confirm':
            focus=QApplication.focusWidget()
            if isinstance(focus,QAbstractButton) and focus.isEnabled():focus.click()
            elif isinstance(focus,QComboBox):focus.showPopup()
        elif action=='back':
            if QApplication.activeModalWidget():QApplication.activeModalWidget().reject()
            else:self.back()
        elif action in {'options','menu'}:
            if not QApplication.activeModalWidget():self.options()
    def poll(self):
        # A button that opens a dialog runs a nested event loop where this timer fires
        # again; without the guard the same press would also answer the dialog.
        if not self.lib or getattr(self,'polling',False):return
        self.polling=True;actions=[]
        try:self.read(actions)
        finally:self.polling=False
        for action in actions:self.dispatch(action)
    def read(self,actions):
        lib=self.lib;lib.SDL_GameControllerUpdate()
        for key,handle in list(self.handles.items()):
            if not lib.SDL_GameControllerGetAttached(handle):lib.SDL_GameControllerClose(handle);del self.handles[key];self.previous.pop(key,None)
        for index in range(lib.SDL_NumJoysticks()):
            # Device indexes shift when a controller is unplugged; instance IDs do not.
            key=lib.SDL_JoystickGetDeviceInstanceID(index) if hasattr(lib,'SDL_JoystickGetDeviceInstanceID') else index
            if key not in self.handles and lib.SDL_IsGameController(index):
                h=lib.SDL_GameControllerOpen(index)
                if h:self.handles[key]=h
        self.connected=[];direction=None
        for index,h in list(self.handles.items()):
            self.connected.append((lib.SDL_GameControllerName(h) or b'Controller').decode(errors='replace'))
            pressed={n:bool(lib.SDL_GameControllerGetButton(h,n)) for n in set(BUTTONS)|set(GAME_BUTTONS)};previous=self.previous.get(index,{})
            if self.game_buttons and not self.window.isActiveWindow() and not QApplication.activeModalWidget():
                for n in GAME_BUTTONS:
                    if pressed[n] and not previous.get(n):self.game_buttons(n)
            for n,action in BUTTONS.items():
                if pressed[n] and not previous.get(n) and action not in {'up','down','left','right'}:actions.append(action)
            for n in [11,12,13,14]:
                if pressed[n]:direction=BUTTONS[n];break
            if not direction:
                x=lib.SDL_GameControllerGetAxis(h,0)/32768;y=lib.SDL_GameControllerGetAxis(h,1)/32768
                if abs(x)>.6 or abs(y)>.6:direction=('right' if x>0 else 'left') if abs(x)>abs(y) else ('down' if y>0 else 'up')
            self.previous[index]=pressed
        now=time.monotonic()
        if direction and (direction!=self.last_dir or now>=self.repeat):actions.append(direction);self.repeat=now+(.12 if direction==self.last_dir else .38)
        self.last_dir=direction
    def close(self):
        self.timer.stop()
        if self.lib:
            for handle in self.handles.values():self.lib.SDL_GameControllerClose(handle)
            self.handles={};self.lib.SDL_QuitSubSystem(0x2000|0x200);self.lib=None

