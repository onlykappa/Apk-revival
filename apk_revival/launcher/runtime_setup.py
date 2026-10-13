"""Guided Waydroid discovery. No privileged host changes are automatic."""
from __future__ import annotations
import ipaddress,os,pathlib,re,subprocess,time,stat,tempfile
from ..runtime import WaydroidRuntime
from ..util import RevivalError,command,tool

class RuntimeManager:
    def __init__(self):self.session_process=None;self.compositor_process=None;self.session_log=None;self.last_start_note=None;self.last={'ready':False,'devices':[],'waydroid':False}
    def environment(self):
        env=dict(os.environ)
        # Gaming Mode can advertise a real Gamescope Wayland socket separately.
        if not env.get('WAYLAND_DISPLAY') and env.get('GAMESCOPE_WAYLAND_DISPLAY'):
            candidate=env['GAMESCOPE_WAYLAND_DISPLAY'];base=pathlib.Path(env.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))
            path=pathlib.Path(candidate) if candidate.startswith('/') else base/candidate
            if path.exists():env['WAYLAND_DISPLAY']=candidate
        # Desktop launchers may omit WAYLAND_DISPLAY even when Weston is running.
        if not env.get('WAYLAND_DISPLAY'):
            base=pathlib.Path(env.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))
            sockets=[]
            for path in sorted(base.glob('wayland-*')):
                try:
                    metadata=path.stat()
                    if stat.S_ISSOCK(metadata.st_mode) and metadata.st_uid==os.getuid():sockets.append(path.name)
                except OSError:pass
            if len(sockets)==1:env['WAYLAND_DISPLAY']=sockets[0]
        from ..util import external_env
        return external_env(env)
    def discover(self,connect=True):
        info={'ready':False,'devices':[],'waydroid':False,'session':'unknown','container':'unknown','service':'unknown','ip':None,'steam_os':False,'wayland':False,'errors':[]}
        try:
            release=pathlib.Path('/etc/os-release').read_text();info['steam_os']='steamos' in release.lower()
        except OSError:pass
        env=self.environment();info['wayland']=bool(env.get('WAYLAND_DISPLAY'))
        try:
            waydroid=tool('waydroid');info['waydroid']=True
            status=re.sub(r'\x1b\[[0-9;]*m','',command([waydroid,'status'],timeout=12,env=env))
            for key,target in [('Session','session'),('Container','container'),('IP address','ip')]:
                m=re.search(r'^\s*'+key+r':[^\S\n]*(.+)$',status,re.M|re.I)
                if m:info[target]=m.group(1).strip() if target=='ip' else m.group(1).strip().upper()
            # A stopped user session can omit Container entirely. Query systemd
            # independently; never infer a stopped service from an omitted field.
            try:
                state=command([tool('systemctl'),'show','waydroid-container.service','--property=ActiveState','--value'],timeout=10,env=env).strip()
                if state in {'active','inactive','failed','activating','deactivating'}:info['service']=state
            except RevivalError as e:info['errors'].append(str(e))
            if connect and info['ip'] and info['ip']!='UNKNOWN':
                try:ip=ipaddress.ip_address(info['ip']);command([tool('adb'),'connect',str(ip)+':5555'],timeout=10)
                except (ValueError,RevivalError) as e:info['errors'].append(str(e))
        except RevivalError as e:info['errors'].append(str(e))
        try:
            output=command([tool('adb'),'devices','-l'],timeout=12)
            for line in output.splitlines()[1:]:
                parts=line.split()
                if len(parts)>=2:info['devices'].append({'serial':parts[0],'state':parts[1],'description':' '.join(parts[2:])})
        except RevivalError as e:info['errors'].append(str(e))
        ready=[d for d in info['devices'] if d['state']=='device'];info['ready']=bool(ready)
        info['binder_available']=pathlib.Path('/dev/binderfs').exists() or any(pathlib.Path('/dev',n).exists() for n in ['binder','anbox-binder'])
        self.last=info;return info
    def open_android_ui(self):
        self.ensure_display()
        subprocess.Popen([tool('waydroid'),'show-full-ui'],env=self.environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return self.discover()
    def connect_manual(self,address):
        value=address.strip()
        if ':' not in value:value+=':5555'
        host,port=value.rsplit(':',1)
        try:ipaddress.ip_address(host);n=int(port);assert 1<=n<=65535
        except (ValueError,AssertionError):raise RevivalError('Enter the Android guest IP address, optionally followed by its port.')
        command([tool('adb'),'connect',value],timeout=12);return self.discover(connect=False)
    def ensure(self,serial=None):
        info=self.discover()
        if not info['ready'] and info['waydroid']:
            if info.get('service')!='active' and info['container'] not in {'RUNNING','FROZEN'}:raise RevivalError('Android container is stopped. In Setup, review and start the Waydroid container with administrator authorization.')
            if info.get('session')!='RUNNING':self.ensure_display()
            if info.get('session')!='RUNNING' and (not self.session_process or self.session_process.poll() is not None):
                self.session_log=tempfile.TemporaryFile(mode='w+b')
                self.session_process=subprocess.Popen([tool('waydroid'),'session','start'],env=self.environment(),stdout=self.session_log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                time.sleep(.5);info=self.discover()
                if info['ready']:break
                if self.session_process and self.session_process.poll() not in (None,0):
                    self.session_log.seek(0);detail=self.session_log.read()[-2500:].decode(errors='replace')
                    raise RevivalError('Waydroid session failed to start: '+detail)
        ready=[d['serial'] for d in info['devices'] if d['state']=='device']
        if serial in ready:return serial
        if len(ready)==1:return ready[0]
        if len(ready)>1:raise RevivalError('More than one Android environment is connected. Choose the intended device in Setup.')
        if any(d['state']=='unauthorized' for d in info['devices']):raise RevivalError('Android needs ADB authorization. Open Android, approve Allow USB debugging (Always allow from this computer), then Check again.')
        detail='; '.join(info.get('errors',[])[-2:])
        raise RevivalError('Android is not connected. '+('Guest IP: '+str(info['ip'])+'. ' if info.get('ip') else '')+'Start Android, wait for its boot screen, then Check again. '+detail)
    def ensure_display(self):
        if self.environment().get('WAYLAND_DISPLAY'):return
        if not os.environ.get('DISPLAY'):raise RevivalError('No display is available. Start APK Revival in Desktop Mode and retry Start Android.')
        try:weston=tool('weston')
        except RevivalError:raise RevivalError('This desktop uses X11 and has no Wayland display. Start your existing Waydroid launcher/Weston first, then Check again. No system packages were changed.')
        base=pathlib.Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))
        socket='apkr-wayland-'+str(os.getpid())
        self.compositor_process=subprocess.Popen([weston,'--backend=x11-backend.so','--socket='+socket,'--width=1280','--height=800','--idle-time=0'],env=self.environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if (base/socket).exists():os.environ['WAYLAND_DISPLAY']=socket;return
            if self.compositor_process.poll() is not None:break
            time.sleep(.2)
        raise RevivalError('The local Weston display could not start. Open your existing Waydroid launcher, then retry Check again.')
    def start_container_authorized(self):
        info=self.discover(connect=False)
        if info.get('service')=='active':
            self.last_start_note='Waydroid container service is already running. Choose Start Android to start the user session.'
            return info
        # The GUI explicitly asks before showing a host administrator prompt.
        if info.get('steam_os'):
            try:terminal=tool('konsole');sudo=tool('sudo')
            except RevivalError:terminal=None
        else:terminal=None
        if terminal:
            command([terminal,'--separate','-e',sudo,tool('systemctl'),'start','waydroid-container.service'],timeout=120,env=self.environment())
        else:
            command([tool('pkexec'),tool('systemctl'),'start','waydroid-container.service'],timeout=90,env=self.environment())
        info=self.discover()
        if info.get('service')!='active' and info['container'] not in {'RUNNING','FROZEN'}:
            raise RevivalError('Waydroid container did not become active. Administrator authorization may have been cancelled or the service failed. Check systemctl status waydroid-container.service in Konsole.')
        self.last_start_note='Container service started. Choose Start Android next; the device list fills after Android boots and ADB connects.'
        return info
    def stop_owned_session(self):
        # Do not stop a shared container/session: only release this launcher-owned helper.
        if self.session_process and self.session_process.poll() is None:
            self.session_process.terminate()
            try:self.session_process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.session_process.kill();self.session_process.wait(timeout=5)
        self.session_process=None
        if self.session_log:self.session_log.close();self.session_log=None
        if self.compositor_process and self.compositor_process.poll() is None:
            self.compositor_process.terminate()
            try:self.compositor_process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.compositor_process.kill();self.compositor_process.wait(timeout=5)
        self.compositor_process=None

class ManagedAndroid(WaydroidRuntime):
    def install(self,store,p,original=False):
        self.compatible(p);self.package=p['analysis']['metadata']['package'] if original else p['restoration'].get('client_package',p['analysis']['metadata']['package'])
        apk=store.base(p) if original else self.artifact(store,p)
        from ..util import digest
        sha=digest(apk);installed=None
        try:
            paths=self.shell('pm','path',self.package).strip().splitlines()
            base=next(x[8:] for x in paths if x.startswith('package:') and x.endswith('/base.apk'))
            installed=self.shell('sha256sum',base).split()[0]
        except (RevivalError,StopIteration,IndexError):pass
        if installed!=sha:super().install(store,p,original);self.installed_now=True
        else:self.installed_now=False
        from ..util import atomic_json,read_json
        receipt=store.directory(p['id'])/'deployments.json'
        saved=read_json(receipt) if receipt.exists() else {}
        signature='|'.join(i['sha256'] for i in p['inputs'] if i['role']=='obb')
        key=str(self.serial)+'|'+self.package
        if not self.installed_now and saved.get(key)!=signature:
            for i in p['inputs']:
                if i['role']=='obb':
                    remote='/sdcard/Android/obb/'+self.package
                    self.shell('mkdir','-p',remote);self.adb('push',store.directory(p['id'])/'originals'/i['stored_name'],remote+'/'+i['name'],timeout=180)
        saved[key]=signature;atomic_json(receipt,saved)
    def launch(self,p):
        super().launch(p)
        # An activity launch is only a launch observation, never an offline gameplay result.
        pid=self.shell('pidof',self.package).strip()
        if not pid:raise RevivalError('The game closed during launch. Export diagnostics to investigate.')
        return pid

