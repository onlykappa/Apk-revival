"""Managed Waydroid startup, graphical authorization, discovery and readiness."""
from __future__ import annotations
import ipaddress,json,os,pathlib,re,subprocess,time,stat,tempfile,signal
from ..runtime import WaydroidRuntime
from ..util import RevivalError,command,tool

class RuntimeManager:
    def __init__(self,state_file=None):
        self.session_process=None;self.compositor_process=None;self.session_log=None;self.bundle_process=None;self.bundle_log=None;self.bundle_log_path=None;self.startup_state_path=None;self.bundle_started_at=None;self.bundle_mode=None;self.last_start_note=None;self.last={'ready':False,'devices':[],'waydroid':False};self.state_file=state_file
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
    def discover(self,connect=True,probe_timeout=12):
        probe_timeout=max(1,min(12,float(probe_timeout)))
        info={'ready':False,'devices':[],'waydroid':False,'session':'unknown','container':'unknown','service':'unknown','ip':None,'steam_os':False,'wayland':False,'errors':[]}
        try:
            release=pathlib.Path('/etc/os-release').read_text();info['steam_os']='steamos' in release.lower()
        except OSError:pass
        env=self.environment();info['wayland']=bool(env.get('WAYLAND_DISPLAY'))
        try:
            waydroid=tool('waydroid');info['waydroid']=True
            status=re.sub(r'\x1b\[[0-9;]*m','',command([waydroid,'status'],timeout=probe_timeout,env=env))
            info['status_output']=status
            for key,target in [('Session','session'),('Container','container'),('IP address','ip'),('Wayland display','wayland_display')]:
                m=re.search(r'^\s*'+key+r':[^\S\n]*(.+)$',status,re.M|re.I)
                if m:info[target]=m.group(1).strip() if target in ('ip','wayland_display') else m.group(1).strip().upper()
            if info.get('ip') in ('UNKNOWN','None',''):info['ip']=None
            # A stopped user session can omit Container entirely. Query systemd
            # independently; never infer a stopped service from an omitted field.
            try:
                state=command([tool('systemctl'),'show','waydroid-container.service','--property=ActiveState','--value'],timeout=min(10,probe_timeout),env=env).strip()
                if state in {'active','inactive','failed','activating','deactivating'}:info['service']=state
            except RevivalError as e:info['errors'].append(str(e))
            if connect and info['ip'] and info['ip']!='UNKNOWN':
                try:ip=ipaddress.ip_address(info['ip']);command([tool('adb'),'connect',str(ip)+':5555'],timeout=min(10,probe_timeout))
                except (ValueError,RevivalError) as e:info['errors'].append(str(e))
        except RevivalError as e:info['errors'].append(str(e))
        try:
            output=command([tool('adb'),'devices','-l'],timeout=probe_timeout)
            for line in output.splitlines()[1:]:
                parts=line.split()
                if len(parts)>=2:info['devices'].append({'serial':parts[0],'state':parts[1],'description':' '.join(parts[2:])})
        except RevivalError as e:info['errors'].append(str(e))
        if info['waydroid'] and info['session']=='RUNNING' and info['container']=='RUNNING' and not info.get('ip'):
            self.discover_bridge_guest(info,connect)
        ready=[d for d in info['devices'] if d['state']=='device'];info['ready']=any(d['serial']==str(info['ip'])+':5555' for d in ready) if info.get('ip') else False
        info['binder_available']=pathlib.Path('/dev/binderfs').exists() or any(pathlib.Path('/dev',n).exists() for n in ['binder','anbox-binder'])
        self.last=info
        if self.state_file:
            if self.bundle_log_path:info['managed_startup_log']=str(self.bundle_log_path)
            try:
                from ..util import atomic_json
                atomic_json(self.state_file,info)
            except OSError:pass
        return info

    def bridge_identity(self):
        """Use this installed container's network identity, not a saved guest IP."""
        try:config=pathlib.Path('/var/lib/waydroid/lxc/waydroid/config').read_text()
        except OSError:return None
        values={}
        for key in ('link','name','hwaddr'):
            match=re.search(r'^lxc\.net\.0\.'+key+r'\s*=\s*(\S+)\s*$',config,re.M)
            if not match:return None
            values[key]=match.group(1)
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',values['link']) or not re.fullmatch(r'[A-Za-z0-9_.-]+',values['name']):return None
        if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',values['hwaddr']):return None
        return values

    def discover_bridge_guest(self,info,connect):
        identity=self.bridge_identity()
        if not identity:
            info['errors'].append('Waydroid reported no IP and its installed bridge identity could not be read.');return
        candidates=[]
        for device in info['devices']:
            if device['state']!='device':continue
            host,separator,port=device['serial'].rpartition(':')
            if separator and port=='5555':
                try:ipaddress.IPv4Address(host);candidates.append((host,device['serial']))
                except ValueError:pass
        # With no usable connected transport, query only this container's own
        # bridge neighbours. No network scanning or fabricated IP addresses.
        if not candidates and connect:
            try:
                neighbors=json.loads(command([tool('ip'),'-j','neigh','show','dev',identity['link']],timeout=3,env=self.environment()))
                matches=0
                for neighbor in neighbors[:128]:
                    if str(neighbor.get('lladdr','')).lower()!=identity['hwaddr'].lower():continue
                    if matches>=4:break
                    matches+=1
                    address=str(ipaddress.IPv4Address(neighbor['dst']));serial=address+':5555'
                    result=command([tool('adb'),'connect',serial],timeout=3)
                    if 'connected to' in result.lower():candidates.append((address,serial))
            except (RevivalError,ValueError,KeyError,TypeError) as error:info['errors'].append('Bridge address discovery: '+str(error))
        verified=[]
        for address,serial in candidates[:4]:
            try:
                guest=WaydroidRuntime(serial)
                mac=guest.shell('cat','/sys/class/net/'+identity['name']+'/address',timeout=2).strip().lower()
                if mac!=identity['hwaddr'].lower():continue
                addresses=guest.shell('ip','-4','addr','show','dev',identity['name'],timeout=2)
                if address not in re.findall(r'\binet\s+(\d+\.\d+\.\d+\.\d+)/',addresses):continue
                verified.append((address,serial))
            except RevivalError as error:info['errors'].append('Guest identity check: '+str(error))
        if len(verified)==1:
            address,serial=verified[0];info['ip']=address;info['ip_source']='verified_container_network_identity'
            if not any(d['serial']==serial and d['state']=='device' for d in info['devices']):info['devices'].append({'serial':serial,'state':'device','description':'Verified Waydroid bridge guest'})
        else:info['errors'].append('Waydroid DHCP address is unavailable; no unique connected guest matched its configured MAC and current interface address.')
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
    def steam_bundle_launcher(self):
        """Use the installed main-profile launcher, never a fresh Waydroid init.

        The SteamOS bundle mounts ~/Android_Waydroid/waydroid.img before starting
        its container. Calling generic Waydroid while it is unmounted can
        incorrectly report that Android is not initialized.
        """
        base=pathlib.Path.home()/'Android_Waydroid'
        launcher=base/'Android_Waydroid_Cage.sh'
        image=base/'waydroid.img'
        if image.is_file() and launcher.is_file() and os.access(launcher,os.X_OK):
            return launcher
        return None

    def start_steam_bundle(self):
        if self.bundle_process and self.bundle_process.poll() is None:return
        if self.bundle_log:self.bundle_log.close();self.bundle_log=None
        import sys
        resources=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources'
        script=resources/'managed-waydroid.sh';askpass=resources/'waydroid-askpass.sh'
        if not script.is_file() or not askpass.is_file():raise RevivalError('Managed Android helpers are missing. Reinstall APK Revival; do not reset Android.')
        askpass.chmod(0o700)
        env=self.environment();env['SUDO_ASKPASS']=str(askpass)
        env['APKR_AUTH_CONTEXT']='1'
        for key in ('WAYLAND_DISPLAY','DISPLAY','XAUTHORITY'):
            env['APKR_AUTH_'+key]=env.get(key,'')
        self.bundle_mode='managed';self.last_start_note='Starting the existing Android image. A graphical authorization prompt may appear.'
        if self.state_file:
            import uuid
            directory=pathlib.Path(self.state_file).parent/'runtime-logs'
            directory.mkdir(mode=0o700,parents=True,exist_ok=True)
            self.bundle_log_path=directory/('managed-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.log')
            fd=os.open(self.bundle_log_path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
            self.bundle_log=os.fdopen(fd,'w+b')
            self.startup_state_path=self.bundle_log_path.with_suffix('.startup')
            fd=os.open(self.startup_state_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as state:state.write('starting\n')
            env['APKR_STARTUP_STATE_FILE']=str(self.startup_state_path)
        else:self.bundle_log=tempfile.TemporaryFile(mode='w+b')
        self.bundle_started_at=time.monotonic()
        try:self.bundle_process=subprocess.Popen(['/bin/bash',str(script)],env=env,stdin=subprocess.DEVNULL,stdout=self.bundle_log,stderr=subprocess.STDOUT,start_new_session=True)
        except Exception:
            self.bundle_log.close();self.bundle_log=None;self.bundle_process=None;raise

    def wait_managed_startup(self,progress=lambda _:None):
        """Do not report Play ready behind an unfinished setup password dialog."""
        if not self.bundle_process or not self.startup_state_path:return
        deadline=(self.bundle_started_at if self.bundle_started_at is not None else time.monotonic())+110
        previous=None
        while time.monotonic()<deadline:
            try:state=self.startup_state_path.read_text()[:128].strip()
            except OSError:state='starting'
            if state=='ready' and self.bundle_process.poll() is None:return
            if state=='failed' or self.bundle_process.poll() is not None:
                raise RevivalError('Android startup setup failed or authorization was cancelled. Check the retained startup log; your saves are preserved.')
            if state!=previous:
                progress('Waiting for runtime setup authorization on the desktop' if state=='authorizing' else 'Waiting for runtime setup to finish')
                previous=state
            time.sleep(.5)
        raise RevivalError('Runtime setup authorization did not finish within 110 seconds. Retry Play and complete the graphical prompt. No game was launched or data reset.')

    def restart_android(self,progress=lambda _:None):
        """Restart the installed main profile without initialization or data changes."""
        if not self.steam_bundle_launcher():raise RevivalError('Managed restart requires the existing SteamOS Waydroid main profile.')
        import sys
        resources=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources'
        askpass=resources/'waydroid-askpass.sh'
        if not askpass.is_file():raise RevivalError('Graphical authorization helper is missing.')
        askpass.chmod(0o700);env=self.environment();env['SUDO_ASKPASS']=str(askpass)
        progress('Checking ownership of the existing Android main profile')
        from .runtime_access import preflight_command
        command(preflight_command(tool('sudo')),timeout=20,env=env)
        progress('Stopping the stale Android session')
        command([tool('waydroid'),'session','stop'],timeout=15,env=env)
        if self.bundle_process and self.bundle_process.poll() is None:
            try:self.bundle_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.signal_owned_bundle(signal.SIGTERM)
                try:self.bundle_process.wait(timeout=5)
                except subprocess.TimeoutExpired:raise RevivalError('The owned Android compositor did not close. Restart was stopped without resetting data.')
        self.bundle_process=None
        if self.bundle_log:self.bundle_log.close();self.bundle_log=None
        progress('Starting the preserved Android image again')
        return self.ensure(progress=progress,_allow_recovery=False)

    def wake_runtime(self,info,progress):
        if info.get('container')=='FROZEN':
            progress('Waking the suspended game runtime')
            # This is the same ContainerManager.Unfreeze call used by Waydroid's
            # own app launch path. It resumes processes without changing saves,
            # disabling suspend or requiring privileged CLI commands.
            command([tool('dbus-send'),'--system','--print-reply','--reply-timeout=10000',
                     '--dest=id.waydro.Container','/ContainerManager',
                     'id.waydro.ContainerManager.Unfreeze'],timeout=12,env=self.environment())
            return self.discover()
        return info

    def check_managed_display(self,info):
        """Verify the existing session's actual private socket, not a cached layer list."""
        display=info.get('wayland_display')
        if not display:return None
        env=self.environment()
        if (display==env.get('WAYLAND_DISPLAY') and env.get('XDG_SESSION_TYPE')=='wayland'
                and env.get('XDG_CURRENT_DESKTOP')=='KDE'):
            # KDE's native compositor does not implement wlr-output-management.
            # Verify its real protocol connection instead of treating that
            # unsupported extension as a dead Android display.
            try:
                outputs=command([tool('wayland-info')],timeout=3,env=env)
                return all("interface: '"+name+"'" in outputs for name in ('wl_compositor','wl_output','xdg_wm_base'))
            except RevivalError:return False
        randr=pathlib.Path.home()/'.local/opt/steamos-waydroid/current/bin/wlr-randr'
        if not randr.is_file():return None
        env['WAYLAND_DISPLAY']=display
        try:
            outputs=command([str(randr)],timeout=2,env=env)
            return bool(re.search(r'^\S+.*\n\s+.*',outputs,re.M))
        except RevivalError:return False

    def ensure(self,serial=None,progress=lambda _:None,_allow_recovery=True):
        progress('Finding the game runtime')
        info=self.wake_runtime(self.discover(),progress)
        if not info['ready'] and info['waydroid']:
            bundle=self.steam_bundle_launcher()
            # Never start another Cage instance over an already-running session.
            if bundle and info.get('session')!='RUNNING':
                progress('Starting the game runtime');self.start_steam_bundle()
                deadline=time.monotonic()+110
                while time.monotonic()<deadline:
                    time.sleep(1)
                    info=self.discover()
                    if info['ready']:info=self.wake_runtime(info,progress);break
                    process=self.bundle_process
                    if process and process.poll() not in (None,0):
                        detail=''
                        if self.bundle_log:
                            self.bundle_log.seek(0)
                            detail=self.bundle_log.read()[-1400:].decode(errors='replace').strip()
                        raise RevivalError('SteamOS Waydroid launcher exited before Android connected. '+
                            (detail or 'Check the installed SteamOS Waydroid bundle and authorization.'))
                if not info['ready']:
                    self.stop_owned_session()
                    raise RevivalError('The game runtime did not connect within 110 seconds. Retry Play or export diagnostics. No data was reset.')
            else:
                if info.get('service')!='active' and info['container'] not in {'RUNNING','FROZEN'}:
                    progress('Starting Android container');self.start_container_authorized()
                if info.get('session')!='RUNNING':self.ensure_display()
                if info.get('session')!='RUNNING' and (not self.session_process or self.session_process.poll() is not None):
                    self.session_log=tempfile.TemporaryFile(mode='w+b')
                    self.session_process=subprocess.Popen([tool('waydroid'),'session','start'],env=self.environment(),stdout=self.session_log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    time.sleep(.5);info=self.discover()
                    if info['ready']:info=self.wake_runtime(info,progress);break
                    if self.session_process and self.session_process.poll() not in (None,0):
                        self.session_log.seek(0);detail=self.session_log.read()[-2500:].decode(errors='replace')
                        raise RevivalError('Waydroid session failed to start: '+detail)
        ready=[d['serial'] for d in info['devices'] if d['state']=='device']
        # Managed Waydroid must never deploy to an unrelated phone/emulator.
        discovered=(str(info['ip'])+':5555') if info.get('ip') and info['ip']!='UNKNOWN' else None
        if discovered in ready:selected=discovered
        elif serial in ready:selected=serial
        else:selected=None
        if selected:
            try:self.wait_managed_startup(progress)
            except RevivalError:
                # Cancel the owned helper/dialog as well as its session. A retry
                # must not leave another password window behind the game.
                self.stop_owned_session();raise
            progress('Waiting for the game runtime to finish starting')
            managed=(selected==discovered and info.get('session')=='RUNNING' and self.steam_bundle_launcher())
            if managed and self.check_managed_display(info) is False:
                if _allow_recovery:
                    progress('The game display disconnected. Restarting its preserved runtime once')
                    return self.restart_android(progress=progress)
                raise RevivalError('The game compositor did not respond on its reported socket after recovery. No game data was reset. Export diagnostics for the display failure.')
            runtime=WaydroidRuntime(selected);deadline=time.monotonic()+45;missing_display=0
            while time.monotonic()<deadline:
                recover=False
                try:
                    boot=runtime.shell('getprop','sys.boot_completed',timeout=3).strip()
                    # Probe the actual endpoint: `service check` can report
                    # SurfaceFlinger absent even when its dumpsys endpoint works.
                    layers=runtime.shell('dumpsys','SurfaceFlinger','--list',timeout=3).strip()
                    absent="Can't find service:" in layers
                    if not layers:
                        services=runtime.shell('service','list',timeout=3)
                        # On this guest dead native services can produce an empty
                        # dumpsys reply. Require an actual list lacking both input
                        # and window, not an empty/failed permission-sensitive probe.
                        absent=bool(re.search(r'Found \d+ services:',services)) and not re.search(r'\b(?:input|window):',services)
                    display_ready=bool(layers) and not re.search(r"Can't find service:|Error:|Permission Denial",layers)
                    if boot=='1' and display_ready:
                        if managed:
                            processes=runtime.shell('ps','-A','-o','NAME',timeout=3)
                            # The composer can die while SurfaceFlinger still returns
                            # cached layer names. A complete process list is required.
                            if re.search(r'^NAME\s*$',processes,re.M) and not re.search(r'android\.hardware\.graphics\.composer[^\s]*service',processes):
                                absent=True;display_ready=False
                        if display_ready and runtime.shell('pm','path','android',timeout=3).strip().startswith('package:'):return selected
                    missing_display=missing_display+1 if absent else 0
                    recover=(boot=='1' and missing_display>=3 and _allow_recovery and info.get('session')=='RUNNING'
                             and selected==discovered and self.steam_bundle_launcher())
                except RevivalError:pass
                # Recovery failure must propagate; never retry authorization or
                # restart recursively after catching its error as a poll failure.
                if recover:
                    progress('The game display service failed. Recovering the existing runtime once; saves are preserved')
                    return self.restart_android(progress=progress)
                time.sleep(.5)
            raise RevivalError('The game runtime connected but boot, package or display services did not become ready within 45 seconds. Recovery is bounded to one attempt. Retry Play or export diagnostics. No data was reset.')
        if len(ready)>1:raise RevivalError('More than one Android environment is connected. Choose the intended device in Setup.')
        if any(d['state']=='unauthorized' for d in info['devices']):raise RevivalError('Android needs ADB authorization. Open Android, approve Allow USB debugging (Always allow from this computer), then Check again.')
        detail='; '.join(info.get('errors',[])[-2:])
        raise RevivalError('The game runtime is not connected. Retry Play or export diagnostics. Your saves are preserved. '+detail)
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
        if self.steam_bundle_launcher():
            # For this installation the container cannot be started in
            # isolation: the persistent image must be mounted first.
            self.ensure()
            return self.last
        info=self.discover(connect=False)
        if info.get('service')=='active':
            self.last_start_note='Waydroid container service is already running. Choose Start Android to start the user session.'
            return info
        command([tool('pkexec'),tool('systemctl'),'start','waydroid-container.service'],timeout=90,env=self.environment())
        info=self.discover()
        if info.get('service')!='active' and info['container'] not in {'RUNNING','FROZEN'}:
            raise RevivalError('Waydroid container did not become active. Administrator authorization may have been cancelled or the service failed. Check systemctl status waydroid-container.service in Konsole.')
        self.last_start_note='Container service started. Choose Start Android next; the device list fills after Android boots and ADB connects.'
        return info
    def stop_owned_session(self):
        # Do not stop a shared container/session: only release this launcher-owned helper.
        if self.bundle_process and self.bundle_process.poll() is None:
            # Closing Cage first breaks Android's live Wayland connection and
            # can abort its composer. Ask the existing session to stop first.
            command([tool('waydroid'),'session','stop'],timeout=15,env=self.environment())
            try:self.bundle_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.signal_owned_bundle(signal.SIGTERM)
                try:self.bundle_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.signal_owned_bundle(signal.SIGKILL);self.bundle_process.wait(timeout=5)
        self.bundle_process=None;self.bundle_started_at=None
        if self.bundle_log:self.bundle_log.close();self.bundle_log=None
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

    def signal_owned_bundle(self,signum):
        """Release only the verified process group created by this launcher."""
        process=self.bundle_process
        if not process or process.poll() is not None:return
        pid=process.pid
        if isinstance(pid,int) and pid>1:
            try:
                if os.getpgid(pid)==pid:
                    os.killpg(pid,signum);return
            except ProcessLookupError:return
        if signum==signal.SIGTERM:process.terminate()
        else:process.kill()

class ManagedAndroid(WaydroidRuntime):
    def __init__(self,serial=None):
        super().__init__(serial);self.previous_policy=None;self.applied_policy=None

    def game_presentation(self,package):
        # Restrict immersive mode to this game. Respect custom user policies.
        prior=self.shell('settings','get','global','policy_control',timeout=3).strip()
        if prior in ('','null','null*'):
            applied='immersive.full='+package
            self.shell('settings','put','global','policy_control',applied,timeout=3)
            self.previous_policy=prior;self.applied_policy=applied

    def restore_presentation(self):
        if self.applied_policy is not None:
            try:
                current=self.shell('settings','get','global','policy_control',timeout=3).strip()
                if current==self.applied_policy:
                    if self.previous_policy in ('','null'):self.shell('settings','delete','global','policy_control',timeout=3)
                    else:self.shell('settings','put','global','policy_control',self.previous_policy,timeout=3)
            finally:self.previous_policy=None;self.applied_policy=None

    def stop(self):
        try:super().stop()
        finally:self.restore_presentation()

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
        package=p['restoration'].get('client_package') or p['analysis']['metadata']['package']
        if not re.fullmatch(r'[A-Za-z0-9_.]+',package):raise RevivalError('Invalid Android package name.')
        self.launch_step('Checking the game display connection')
        manager=RuntimeManager();info=manager.discover(connect=False)
        if self.serial==str(info.get('ip'))+':5555':manager.wake_runtime(info,lambda _:None)
        if self.serial==str(info.get('ip'))+':5555' and manager.check_managed_display(info) is False:
            raise RevivalError('The game display disconnected before activity launch. Retry Play to recover it; saves are preserved.')
        self.launch_step('Applying game window presentation')
        self.game_presentation(package)
        super().launch(p)
        # An activity launch is only a launch observation, never an offline gameplay result.
        pid=self.shell('pidof',self.package,timeout=3).strip()
        if not pid:raise RevivalError('The game closed during launch. Export diagnostics to investigate.')
        return pid


