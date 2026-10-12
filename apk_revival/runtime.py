"""Android runtime boundary. The launcher manages an existing Waydroid runtime."""
from __future__ import annotations
import pathlib, re, shlex, time, uuid, xml.etree.ElementTree as ET
from .backend import Backend
from .util import RevivalError, atomic_json, command, digest, now, tool

class WaydroidRuntime:
    def __init__(self,serial=None):self.serial=serial;self.backend=None;self.forward_port=None;self.package=None
    def adb(self,*args,timeout=60,input=None):
        if not self.serial:raise RevivalError('Set a specific runtime ADB serial. Get the Waydroid IP from Android Settings > About, run adb connect IP:5555, then configure that serial.')
        return command([tool('adb'),'-s',self.serial,*args],timeout=timeout,input=input)
    def shell(self,*args,timeout=60):
        # ADB joins shell arguments; shell-quote each token even when subprocess has no shell.
        return self.adb('shell',' '.join(shlex.quote(str(a)) for a in args),timeout=timeout)
    def probe(self):
        tools={}
        for name in ['waydroid','adb','apktool','java','zipalign','apksigner','keytool']:
            try:tools[name]=tool(name)
            except RevivalError:tools[name]=None
        import os
        if os.getenv('APKR_APKTOOL_JAR'):tools['apktool']='java -jar '+os.getenv('APKR_APKTOOL_JAR')
        report={'adapter':'waydroid','tools':tools,'serial':self.serial,'available':False,'instructions':['Install/initialize Waydroid separately; APK Revival does not install Android.','Start the Waydroid session. Get guest IP from Android Settings > About.','adb connect GUEST_IP:5555; select that exact serial in Runtime settings.']}
        if not tools['adb'] or not self.serial:return report
        try:
            if self.adb('get-state').strip()!='device':raise RevivalError('ADB device not ready')
            report.update(available=True,abis=self.shell('getprop','ro.product.cpu.abilist').strip().split(','),sdk=self.shell('getprop','ro.build.version.sdk').strip(),release=self.shell('getprop','ro.build.version.release').strip())
        except RevivalError as e:report['error']=str(e)
        return report
    def compatible(self,p):
        r=self.probe()
        if not r['available']:raise RevivalError('Runtime unavailable. '+r.get('error','Connect the configured Waydroid ADB serial first.'))
        required=p['analysis']['abis']
        if required and not set(required)&set(r['abis']):raise RevivalError(f'Architecture mismatch: APK {required}, Android {r["abis"]}. Configure a compatible runtime or ARM translation separately.')
        sdk=p['analysis']['metadata']['min_sdk']
        if sdk and sdk.isdigit() and int(sdk)>int(r['sdk']):raise RevivalError('Android runtime SDK is too old')
        if p['analysis']['input_errors']:raise RevivalError('Input split mismatch must be fixed')
        return r
    def artifact(self,store,p):
        rel=p['restoration'].get('artifact')
        if not rel:raise RevivalError('Prepare a restoration first. Use diagnostics to observe the original separately.')
        d=store.directory(p['id']);path=(d/rel).resolve()
        if d.resolve() not in path.parents or digest(path)!=p['restoration']['artifact_sha256']:raise RevivalError('Restored artifact missing, changed or outside its working directory. Prepare again.')
        return path
    def install(self,store,p,original=False):
        self.compatible(p);self.package=p['analysis']['metadata']['package'] if original else p['restoration'].get('client_package',p['analysis']['metadata']['package'])
        apk=store.base(p) if original else self.artifact(store,p)
        split=[store.directory(p['id'])/'originals'/i['stored_name'] for i in p['inputs'] if i['role']=='split_apk']
        self.adb('install-multiple' if split else 'install','-r',apk,*split,timeout=180)
        for i in p['inputs']:
            if i['role']=='obb':
                remote='/sdcard/Android/obb/'+self.package
                self.shell('mkdir','-p',remote);self.adb('push',store.directory(p['id'])/'originals'/i['stored_name'],remote+'/'+i['name'],timeout=180)
    def start(self,store,p):
        if self.backend or self.package:raise RevivalError('Stop the current game before launching another')
        if p['restoration']['path']=='rebuild':raise RevivalError('Use the separate rebuild launcher')
        try:
            self.install(store,p)
            if p['restoration']['path']=='local_backend':self.start_backend(store,p)
            self.launch(p);return {'package':self.package,'backend':bool(self.backend),'guest_backend_probed':bool(self.backend)}
        except Exception:
            self.stop();raise
    def launch(self,p):
        package=p['restoration'].get('client_package',p['analysis']['metadata']['package']);self.package=package
        # Resolve the actual launcher instead of picking an arbitrary manifest activity.
        component=self.shell('cmd','package','resolve-activity','--brief',package).strip().splitlines()[-1]
        if '/' not in component or ' ' in component:raise RevivalError('No launchable activity resolved; inspect manifest and logs')
        self.shell('am','start','-W','-n',component)
    def start_backend(self,store,p):
        port=p['runtime']['backend_port']
        if p.get('adapter')=='tapquest-v1':self.backend=Backend(store.directory(p['id'])/'saves/tapquest.json',port).start()
        elif p.get('adapter')=='meego-1.32':
            from .meego.backend import MeegoBackend,config_path
            self.backend=MeegoBackend(store.directory(p['id']),config_path(store,p),port).start()
        else:raise RevivalError('No implemented backend adapter')
        try:
            self.adb('reverse','--no-rebind',f'tcp:{port}',f'tcp:{port}');self.forward_port=port
            self.probe_backend()
        except Exception:
            self.stop_backend();raise
    def probe_backend(self):
        port=self.backend.port
        request='GET /health HTTP/1.0\r\nHost: localhost\r\n\r\n'
        response=self.adb('shell',f'toybox nc -w 3 127.0.0.1 {port}',input=request,timeout=10)
        if self.backend.token not in response:raise RevivalError('Android-to-host backend probe failed. Install a guest toybox nc, check adb reverse, and retry. Host localhost is not assumed to be guest localhost.')
        return response
    def stop_backend(self):
        if self.forward_port:
            try:self.adb('reverse','--remove',f'tcp:{self.forward_port}')
            except RevivalError:pass
            self.forward_port=None
        if self.backend:self.backend.stop();self.backend=None
    def stop(self):
        try:
            if self.package:self.shell('am','force-stop',self.package)
        finally:self.stop_backend();self.package=None
    def diagnostics(self,store,p,original=False):
        self.install(store,p,original=original);self.launch(p)
        time.sleep(2)
        d=store.directory(p['id'])/'diagnostics'/uuid.uuid4().hex;d.mkdir(parents=True)
        (d/'logcat.txt').write_text(self.adb('logcat','-d','-v','threadtime',timeout=30))
        (d/'package.txt').write_text(self.shell('dumpsys','package',p['analysis']['metadata']['package']))
        atomic_json(d/'runtime.json',self.probe());return {'directory':str(d),'notice':'Runtime observation only. Network has not been blocked; no offline verification claim.'}
    def tap_text(self,text):
        self.shell('uiautomator','dump','/sdcard/apkr-window.xml',timeout=20)
        xml=self.shell('cat','/sdcard/apkr-window.xml');root=ET.fromstring(xml[xml.find('<?xml'):])
        for e in root.iter('node'):
            if e.attrib.get('text')==text:
                nums=[int(x) for x in re.findall(r'\d+',e.attrib['bounds'])];self.shell('input','tap',(nums[0]+nums[2])//2,(nums[1]+nums[3])//2);return
        raise RevivalError('UI verification could not find '+text)
    def fixture_event(self,event,timeout=10):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            text=self.adb('logcat','-d','-s','APKRevival:I','*:S')
            matches=re.findall(r'APKR_EVENT (\{[^\n]+\})',text)
            import json
            for line in reversed(matches):
                try:
                    value=json.loads(line)
                    if value.get('event')==event:return value
                except ValueError:pass
            time.sleep(.25)
        raise RevivalError('Timed out waiting for fixture gameplay event: '+event)

class OfflineGuard:
    """Temporary guest-wide egress deny for both IP families, preserving ADB replies.

    Requires guest root. The host firewall is never changed. No silent partial mode.
    """
    def __init__(self,runtime):self.runtime=runtime;self.chain='APKR_'+uuid.uuid4().hex[:10];self.created=[];self.attached=[];self.evidence={}
    def root(self,*args):return self.runtime.shell('su','0',*args)
    def __enter__(self):
        try:
            if self.root('id','-u').strip()!='0':raise RevivalError('Guest root is required to enforce offline verification')
            for family in ['iptables','ip6tables']:
                self.root(family,'-N',self.chain);self.created.append(family)
                self.root(family,'-A',self.chain,'-o','lo','-j','ACCEPT')
                # Waydroid's adbd owns TCP 5555. Its replies carry local control/reverse traffic.
                for uid in ('0','2000'):
                    self.root(family,'-A',self.chain,'-p','tcp','--sport','5555','-m','owner','--uid-owner',uid,'-j','ACCEPT')
                self.root(family,'-A',self.chain,'-j','REJECT')
                self.root(family,'-I','OUTPUT','1','-j',self.chain);self.attached.append(family)
                self.evidence[family]=self.root(family,'-S',self.chain)+self.root(family,'-S','OUTPUT')
            # Inspect routes and firewall enforcement. A failed connection is only secondary evidence.
            self.evidence['routes']=self.runtime.shell('ip','route')
            try:self.runtime.adb('shell','toybox nc -w 2 1.1.1.1 443',input='',timeout=5)
            except RevivalError as e:
                if any(x in str(e).lower() for x in ['unknown option','not found','missing tool']):raise RevivalError('External probe tool unavailable; cannot verify blocking') from e
                self.evidence['negative_probe']='Guest external TCP connection rejected/failed under verified deny rules'
            else:raise RevivalError('External negative probe succeeded; refusing offline verification')
            return self
        except Exception:self.__exit__(None,None,None);raise
    def __exit__(self,*_):
        errors=[]
        for family in reversed(self.attached):
            try:self.root(family,'-D','OUTPUT','-j',self.chain)
            except RevivalError as e:errors.append(str(e))
        for family in reversed(self.created):
            try:self.root(family,'-F',self.chain);self.root(family,'-X',self.chain)
            except RevivalError as e:errors.append(str(e))
        self.attached=[];self.created=[]
        if errors:raise RevivalError('Guest firewall cleanup failed. Run recovery commands from docs/VERIFICATION.md. Chain: '+self.chain+'; '+'; '.join(errors))
