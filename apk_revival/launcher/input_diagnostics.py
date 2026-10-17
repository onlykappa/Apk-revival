"""Read-only input/rendering capture. Never starts/stops Android or changes settings."""
import os,pathlib,re,time,uuid,sys,json
from ..util import command,tool,RevivalError,atomic_json,now,digest
from ..runtime import WaydroidRuntime

LABELS=('Game window: touchscreen pinch and drag','Game window: mouse or trackpad','Android screen: touchscreen','Android screen: mouse or trackpad')

def frame_records(text):
    header=None;records={}
    for line in text.splitlines():
        fields=[value.strip() for value in line.split(',')]
        if 'IntendedVsync' in fields and 'FrameCompleted' in fields:header=fields;continue
        if not header or len(fields)<len(header):continue
        try:row=dict(zip(header,map(int,fields[:len(header)])))
        except ValueError:continue
        start=row['IntendedVsync'];end=row['FrameCompleted']
        if row.get('Flags',0)==0 and 0<start<end<2**63-1:records[start]=end
    return records

def frame_summary(before,after):
    old=frame_records(before);new=frame_records(after)
    samples=sorted((end-start)/1e6 for start,end in new.items() if start not in old)
    def percentile(fraction):return samples[int((len(samples)-1)*fraction+.5)] if samples else None
    return {'metric':'Guest HWUI IntendedVsync to FrameCompleted; NOT touchscreen latency or input-to-photon latency',
            'new_frames':len(samples),'median_ms':percentile(.5),'p95_ms':percentile(.95),
            'coverage':'HWUI frames only. Native OpenGL/SurfaceView gameplay can be absent. Zero samples mean unknown, not smooth rendering.',
            'retained_window_only':True}

def focused_package(text,input_text=''):
    for line in text.splitlines():
        if 'mCurrentFocus' in line:
            match=re.search(r'\b([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/',line)
            if match:return match.group(1)
    # `dumpsys window windows` on this guest omits mCurrentFocus. The input
    # dispatcher's focused window is authoritative; app-layer names alone aren't.
    match=re.search(r'FocusedWindows:\s*\n\s*displayId=\d+, name=[^\n]*?\b([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/',input_text)
    return match.group(1) if match else None

def surface_summary(text):
    rows=[]
    for line in text.splitlines():
        parts=line.split()
        if len(parts)!=3:continue
        try:row=tuple(map(int,parts))
        except ValueError:continue
        if all(0<value<2**63-1 for value in row):rows.append(row)
    presented=sorted({row[1] for row in rows})
    intervals=sorted((b-a)/1e6 for a,b in zip(presented,presented[1:]))
    def percentile(f):return intervals[int((len(intervals)-1)*f+.5)] if intervals else None
    return {'metric':'SurfaceFlinger actual-present timestamp intervals; NOT physical touch latency',
            'unique_presentations':len(presented),'median_interval_ms':percentile(.5),'p95_interval_ms':percentile(.95),
            'max_interval_ms':max(intervals) if intervals else None,
            'retained_duration_ms':(presented[-1]-presented[0])/1e6 if len(presented)>1 else None,
            'limit':'Recent layer buffer only; not a whole-trial FPS measurement or proof of host display timing.'}

def input_summary(text,package):
    if not package:return {'available':False}
    connections=text.split('  Connections:',1)[-1] if '  Connections:' in text else ''
    waits=[]
    for block in re.split(r'\n(?=    \d+: channelName=)',connections):
        first=block.splitlines()[0] if block.splitlines() else ''
        if package+'/' not in first:continue
        waits.extend(int(value) for value in re.findall(r'MotionEvent,[^\n]*wait=(\d+)ms',block))
    return {'available':bool(connections),'pending_motion_events':len(waits),'max_ack_wait_ms':max(waits) if waits else None,
            'limit':'Dispatcher snapshot of unacknowledged game events. Not touch-to-photon latency or a missed-tap count.'}

def collect(launcher,label,ctx,duration=10,settle=3):
    if label not in LABELS:raise RevivalError('Choose a supported diagnostic comparison label.')
    if not 1<=duration<=20 or not 0<=settle<=5:raise RevivalError('Diagnostic duration is outside the bounded capture range.')
    directory=launcher.store.root/'input-diagnostics'/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    directory.mkdir(parents=True,mode=0o700)
    report={'schema_version':1,'time':now(),'label':label,'changes_applied':[],
            'physical_touch_latency_ms':None,'measured_comparison':False,'files':{},'errors':{},
            'session_hints':{key:os.environ.get(key) for key in ('XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP','DISPLAY','WAYLAND_DISPLAY','GAMESCOPE_WAYLAND_DISPLAY')}}
    def capture(name,operation):
        try:
            value=operation();path=directory/(name+'.txt');path.write_text(value,encoding='utf-8');path.chmod(0o600)
            report['files'][name]={'file':path.name,'sha256':digest(path)}
            if re.search(r"(?im)^(?:cmd: )?Can't find service:|^Error:.*service",value):report['errors'][name]='Android reported an unavailable service: '+value.strip()[:500]
            return value
        except (RevivalError,OSError) as error:report['errors'][name]=str(error);return ''
    ctx.step('Reading display and session information')
    env=launcher.runtime_manager.environment()
    env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
    report['host_hardware']=host_hardware()
    status=capture('waydroid-status',lambda:command([tool('waydroid'),'status'],timeout=5,env=env))
    capture('host-displays',lambda:command([tool('xrandr'),'--current'],timeout=5,env=env))
    session=os.environ.get('XDG_SESSION_ID')
    if session and re.fullmatch(r'[A-Za-z0-9_-]+',session):
        capture('host-session',lambda:command([tool('loginctl'),'show-session',session,'--property=Type','--property=Active','--property=Name'],timeout=5,env=env))
    # Query the socket declared by this Android session; never guess a display name.
    display=re.search(r'^\s*Wayland display:\s*(\S+)',status,re.M)
    if display:
        nested=dict(env,WAYLAND_DISPLAY=display.group(1));report['android_wayland_display']=display.group(1)
        randr=pathlib.Path.home()/'.local/opt/steamos-waydroid/current/bin/wlr-randr'
        if display.group(1)==env.get('WAYLAND_DISPLAY'):
            capture('android-compositor-outputs',lambda:command([tool('wayland-info')],timeout=5,env=nested))
        elif randr.is_file():capture('android-compositor-outputs',lambda:command([randr],timeout=5,env=nested))
    else:report['errors']['android-compositor-outputs']='Android session did not declare its Wayland display; no socket guessed.'
    script=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources/managed-waydroid.sh'
    if script.is_file():report['launcher_script_sha256']=digest(script)
    serial=launcher.active.get('serial') if launcher.active and launcher.active.get('kind')=='android' else None
    if not serial:
        try:
            info=launcher.runtime_manager.discover(connect=False)
            current=str(info.get('ip'))+':5555';serial=current if any(d['serial']==current and d['state']=='device' for d in info['devices']) else None
        except RevivalError as error:report['errors']['android-discovery']=str(error)
    if not serial:
        report['errors']['android']='No current Android connection. This read-only capture does not start Android or use a stale saved IP.'
    else:
        report['serial']=serial;runtime=WaydroidRuntime(serial)
        capture('android-size',lambda:runtime.shell('wm','size',timeout=5))
        capture('android-density',lambda:runtime.shell('wm','density',timeout=5))
        for property_name in ('persist.waydroid.fake_touch','persist.waydroid.width','persist.waydroid.height','persist.waydroid.multi_windows','ro.dalvik.vm.native.bridge'):
            capture('prop-'+property_name,lambda key=property_name:runtime.shell('getprop',key,timeout=5))
        for seconds in range(settle,0,-1):ctx.step(f'Switch back to Android: capture starts in {seconds} seconds');time.sleep(1)
        window=capture('window-before',lambda:runtime.shell('dumpsys','window','windows',timeout=5))
        input_before=capture('input-before',lambda:runtime.shell('dumpsys','input',timeout=5))
        package=focused_package(window,input_before);report['focused_android_package']=package
        before=capture('frames-before',lambda:runtime.shell('dumpsys','gfxinfo',package,'framestats',timeout=5)) if package else ''
        services_missing=any(key in report['errors'] for key in ('android-size','android-density','window-before','input-before','frames-before'))
        if not window.strip() and not input_before.strip():
            services=capture('android-service-list',lambda:runtime.shell('service','list',timeout=5))
            if re.search(r'Found \d+ services:',services) and not re.search(r'\b(?:input|window):',services):
                services_missing=True;report['errors']['android-services']='The connected runtime has no input/window services; gesture capture is unavailable.'
        report['android_services_missing']=services_missing
        layers=capture('surface-layers-before',lambda:runtime.shell('dumpsys','SurfaceFlinger','--list',timeout=5))
        matching=[line for line in layers.splitlines() if package and package+'/' in line]
        selected_layers=sorted(matching,key=lambda line:('(BLAST)' not in line,'SurfaceView' not in line))[:4]
        report['surface_layers_sampled']=selected_layers
        report['surface_stats_limit']='Reported layers only, bounded recent buffers; raw SurfaceFlinger timestamps are not physical touch latency.'
        for index,layer in enumerate(selected_layers):
            capture(f'surface-{index}-before',lambda selected=layer:runtime.shell('dumpsys','SurfaceFlinger','--latency',selected,timeout=5))
        started=time.monotonic()
        report['input_snapshots']=[]
        for seconds in range(0 if services_missing else duration,0,-1):
            ctx.step(f'Repeat the same gestures in the game: {seconds} seconds remaining');time.sleep(1)
            if seconds%2==0:
                snapshot=capture(f'input-during-{seconds}',lambda:runtime.shell('dumpsys','input',timeout=5))
                report['input_snapshots'].append({'elapsed_seconds':time.monotonic()-started,**input_summary(snapshot,package)})
        report['gesture_window_seconds']=time.monotonic()-started
        capture('input-after',lambda:runtime.shell('dumpsys','input',timeout=5))
        report['surface_summaries']=[]
        for index,layer in enumerate(selected_layers):
            sampled=capture(f'surface-{index}-after',lambda selected=layer:runtime.shell('dumpsys','SurfaceFlinger','--latency',selected,timeout=5))
            report['surface_summaries'].append({'layer':layer,**surface_summary(sampled)})
        after=capture('frames-after',lambda:runtime.shell('dumpsys','gfxinfo',package,'framestats',timeout=5)) if package else ''
        final_window=capture('window-after',lambda:runtime.shell('dumpsys','window','windows',timeout=5))
        final_input=capture('input-focus-after',lambda:runtime.shell('dumpsys','input',timeout=5))
        report['focus_changed']=focused_package(final_window,final_input)!=package
        if package:report['frame_summary']=frame_summary(before,after)
        capture('surface-layers',lambda:runtime.shell('dumpsys','SurfaceFlinger','--list',timeout=5))
        def relevant_logs():
            logs=runtime.adb('logcat','-d','-t','200',timeout=5)
            return '\n'.join(line for line in logs.splitlines() if re.search(r'InputDispatcher|InputReader|Choreographer|Skipped.*frames|OpenGLRenderer|SurfaceFlinger|FATAL EXCEPTION|Fatal signal',line))
        capture('input-render-log',relevant_logs)
        capture('graphics-crash-log',lambda:runtime.adb('logcat','-b','crash','-d','-t','120',timeout=5))
    report['physical_test_results']='User-labelled capture only; repeat tap/edge/drag/zoom delivery and perceived responsiveness require observations. No before/after improvement is inferred.'
    atomic_json(directory/'report.json',report)
    return {'directory':str(directory),'android_captured':bool(serial),'report':report}

def host_hardware():
    facts={'input_devices':[],'kernel_connectors':[],'saved_kwin_outputs':[],
           'limit':'Saved KWin modes/scale/rotation are not proof of active compositor geometry or refresh rate.'}
    for path in sorted(pathlib.Path('/sys/class/input').glob('event*/device')):
        try:
            name=(path/'name').read_text().strip();properties=(path/'properties').read_text().strip()
            facts['input_devices'].append({'event':path.parent.name,'name':name,'properties_bitmap':properties,
                                          'absolute_axes_bitmap':(path/'capabilities/abs').read_text().strip()})
        except OSError:pass
    for path in sorted(pathlib.Path('/sys/class/drm').glob('card*-*')):
        try:facts['kernel_connectors'].append({'connector':path.name,'status':(path/'status').read_text().strip()})
        except OSError:pass
    config=pathlib.Path.home()/'.config/kwinoutputconfig.json'
    try:
        for section in json.loads(config.read_text()):
            if section.get('name')=='outputs':
                for output in section['data']:facts['saved_kwin_outputs'].append({key:output.get(key) for key in ('connectorName','mode','scale','transform')})
    except (OSError,ValueError,TypeError,KeyError):pass
    return facts
