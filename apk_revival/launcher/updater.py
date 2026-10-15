"""GitHub updates: verify, stage, close cleanly, swap with rollback, restart."""
from __future__ import annotations
import hashlib,json,os,pathlib,posixpath,re,shutil,subprocess,sys,tarfile,tempfile,time,urllib.error,urllib.request
from .. import __version__
from ..util import RevivalError,external_env
from .network import open_url

REPO='onlykappa/Apk-revival'
API='https://api.github.com/repos/'+REPO
RELEASES='https://github.com/'+REPO+'/releases'
MAX_ARCHIVE=512*1024*1024
MAX_EXPANDED=2*1024*1024*1024


def version(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',value)
    if not match:raise RevivalError('Unsupported update version')
    return tuple(map(int,match.groups()))


class Updater:
    def __init__(self,token=None):self.token=token or os.getenv('APKR_GITHUB_TOKEN');self.release=None
    def request(self,url,asset=False):
        # Credentials only go to the GitHub API, never to redirected asset hosts.
        if not url.startswith(API+'/'):raise RevivalError('Unexpected update origin')
        headers={'User-Agent':'APK-Revival/'+__version__,'Accept':'application/octet-stream' if asset else 'application/vnd.github+json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request(url,headers=headers)
        if not self.token:return open_url(request)
        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,hdrs,newurl):
                redirected=super().redirect_request(req,fp,code,msg,hdrs,newurl)
                if redirected:
                    if not newurl.startswith('https://'):raise RevivalError('Insecure update redirect refused')
                    redirected.remove_header('Authorization')
                return redirected
        from .network import tls_context
        opener=urllib.request.build_opener(Redirect(),urllib.request.HTTPSHandler(context=tls_context()))
        return opener.open(request,timeout=45)
    def check(self,progress=lambda _:None):
        progress('Checking GitHub releases')
        try:
            with self.request(API+'/releases?per_page=100') as response:
                raw=response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:raise RevivalError('GitHub release metadata is too large')
            releases=json.loads(raw)
        except urllib.error.HTTPError as error:
            if error.code in (401,403,404):raise RevivalError('GitHub releases are private or access was refused. Use GitHub access with a read-only token, or Open releases then Install downloaded update. Your token is kept only until the app closes.') from error
            raise RevivalError('GitHub update check failed (HTTP '+str(error.code)+'). Retry later.') from error
        candidates=[]
        for item in releases:
            if item.get('draft'):continue
            try:v=version(item['tag_name'])
            except (RevivalError,KeyError):continue
            name='APK-Revival-'+'.'.join(map(str,v))+'-linux-x86_64.tar.gz'
            assets={a['name']:a for a in item.get('assets',[])}
            if name in assets and 'SHA256SUMS.txt' in assets and v>version(__version__):
                candidates.append((v,item,assets[name],assets['SHA256SUMS.txt']))
        if not candidates:self.release=None;return {'available':False,'version':__version__}
        v,item,package,checksums=max(candidates,key=lambda x:x[0])
        self.release={'available':True,'version':'.'.join(map(str,v)),'package':package,'checksums':checksums,'notes':item.get('body',''),'url':RELEASES+'/tag/'+item['tag_name']}
        return self.release
    def stage(self,progress=lambda _:None):
        if not self.release:raise RevivalError('Check for updates first')
        progress('Checking published checksums')
        with self.request(self.release['checksums']['url'],asset=True) as response:raw=response.read(65537)
        if len(raw)>65536:raise RevivalError('Checksum metadata too large')
        hashes={}
        for line in raw.decode('utf-8').splitlines():
            match=re.fullmatch(r'([0-9a-f]{64})\s+\*?([^/\\]+)',line)
            if match:hashes[match[2]]=match[1]
        asset=self.release['package'];expected=hashes.get(asset['name'])
        if not expected:raise RevivalError('No published checksum for this update')
        cache=pathlib.Path.home()/'.cache/apk-revival/updates';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            archive=pathlib.Path(temp)/'update.tar.gz';progress('Downloading APK Revival '+self.release['version'])
            hasher=hashlib.sha256();size=0
            with self.request(asset['url'],asset=True) as response,archive.open('wb') as out:
                while block:=response.read(1024*1024):
                    size+=len(block)
                    if size>MAX_ARCHIVE:raise RevivalError('Update download exceeds the supported size')
                    hasher.update(block);out.write(block)
            if hasher.hexdigest()!=expected:raise RevivalError('Update checksum did not match. Your installed app was not changed.')
            return stage_archive(archive,progress,self.release['version'])


def stage_archive(archive,progress=lambda _:None,expected_version=None):
    cache=pathlib.Path.home()/'.cache/apk-revival/updates';cache.mkdir(parents=True,exist_ok=True)
    destination=pathlib.Path(tempfile.mkdtemp(prefix='staged-',dir=cache))
    try:
        progress('Validating and staging the update')
        with tarfile.open(archive,'r:gz') as tar:
            members=tar.getmembers();seen=set();expanded=0
            for member in members:
                path=pathlib.PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!='APK-Revival':raise RevivalError('Unsafe update archive path')
                if member.name in seen:raise RevivalError('Duplicate update archive path')
                seen.add(member.name);expanded+=member.size
                if expanded>MAX_EXPANDED or len(seen)>50000:raise RevivalError('Update archive too large')
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):raise RevivalError('Unsupported update archive entry')
                if member.issym() or member.islnk():
                    target=posixpath.normpath(posixpath.join(str(path.parent),member.linkname) if member.issym() else member.linkname)
                    if member.linkname.startswith('/') or not target.startswith('APK-Revival/'):raise RevivalError('Update link escapes the application')
            tar.extractall(destination,filter='data')
        app=destination/'APK-Revival';exe=app/'APK-Revival'
        if not exe.is_file() or not (app/'_internal').is_dir():raise RevivalError('Not an APK Revival Linux package')
        for path in app.rglob('*'):
            if not path.resolve().is_relative_to(app.resolve()):raise RevivalError('Update path escapes the application')
        exe.chmod(exe.stat().st_mode|0o111)
        # New builds provide a headless probe. No game, runtime or data directory is opened.
        result=subprocess.run([str(exe),'--update-probe'],capture_output=True,text=True,timeout=25,env=external_env())
        if result.returncode:raise RevivalError('The update cannot start on this system. Your current app was not changed.')
        try:probe=json.loads(result.stdout)
        except ValueError:raise RevivalError('Invalid update compatibility report')
        new=probe.get('version','');version(new)
        if expected_version and new!=expected_version:raise RevivalError('Update version did not match GitHub metadata')
        if version(new)<=version(__version__):raise RevivalError('Choose a newer version of APK Revival')
        if not probe.get('certificates'):raise RevivalError('The update is missing its certificate bundle')
        return {'directory':str(app),'version':new}
    except Exception:
        shutil.rmtree(destination,ignore_errors=True);raise


def restart_with_update(stage):
    if not getattr(sys,'frozen',False):raise RevivalError('Install updates from the packaged Linux application')
    args=[str(pathlib.Path(stage['directory'])/'APK-Revival'),'--apply-update',stage['directory'],'--wait-pid',str(os.getpid())]
    if '--fullscreen' in sys.argv:args.append('--fullscreen')
    if '--data' in sys.argv:
        index=sys.argv.index('--data');args.extend(['--data',sys.argv[index+1]])
    subprocess.Popen(args,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=external_env())


def apply_update(source,pid,fullscreen=False,data=None):
    # Execute from the staged version after the old process has released Qt and saves.
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        try:os.kill(pid,0)
        except ProcessLookupError:break
        time.sleep(.2)
    else:raise RevivalError('The old app did not exit. No update was installed.')
    from .install import install
    result=install(source)
    args=[result['executable']]
    if fullscreen:args.append('--fullscreen')
    if data:args.extend(['--data',data])
    subprocess.Popen(args,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=external_env())
    return 0

