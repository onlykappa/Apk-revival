"""Install preparation dependencies into a user cache, with verified downloads."""
from __future__ import annotations
import hashlib,json,os,pathlib,shutil,tarfile,tempfile,urllib.request,zipfile
from ..util import RevivalError,atomic_json,command,safe_member,tool
from .network import open_url

DOWNLOADS={
 'buildtools.zip':('https://dl.google.com/android/repository/build-tools_r35_linux.zip','bd3a4966912eb8b30ed0d00b0cda6b6543b949d5ffe00bea54c04c81e1561d88'),
 'platformtools.zip':('https://dl.google.com/android/repository/platform-tools_r37.0.1-linux.zip','d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1'),
 'apktool.jar':('https://github.com/iBotPeaches/Apktool/releases/download/v2.12.1/apktool_2.12.1.jar','66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa')}

def cache_root():return pathlib.Path(os.environ.get('APKR_TOOLS',pathlib.Path.home()/'.cache/apk-revival/tools')).expanduser().resolve()

def configure(root=None):
    root=pathlib.Path(root or cache_root())
    values={'APKR_ADB':root/'platform-tools/adb','APKR_APKSIGNER':root/'android-15/apksigner','APKR_ZIPALIGN':root/'android-15/zipalign','APKR_APKTOOL_JAR':root/'apktool.jar','APKR_JAVA':root/'jre/bin/java','APKR_KEYTOOL':root/'jre/bin/keytool'}
    for key,path in values.items():
        if key not in os.environ and path.is_file():os.environ[key]=str(path)
    # SDK launch scripts invoke bare java, not APKR_JAVA. Give subprocesses
    # the same private runtime used by the Python preparation code.
    java=pathlib.Path(os.environ.get('APKR_JAVA',root/'jre/bin/java'))
    if java.is_file():
        bindir=java.resolve().parent
        os.environ['JAVA_HOME']=str(bindir.parent)
        paths=os.environ.get('PATH','').split(os.pathsep)
        os.environ['PATH']=os.pathsep.join([str(bindir)]+[p for p in paths if p!=str(bindir)])
    return values

def health(root=None):
    configure(root);report={}
    for name in ['adb','java','keytool','zipalign','apksigner']:
        try:report[name]={'ready':True,'path':tool(name)}
        except RevivalError:report[name]={'ready':False,'path':None}
    jar=os.getenv('APKR_APKTOOL_JAR');report['apktool']={'ready':bool(jar and pathlib.Path(jar).is_file()) or bool(shutil.which('apktool')),'path':jar or shutil.which('apktool')}
    report['preparation_ready']=all(report[n]['ready'] for n in ['java','keytool','zipalign','apksigner']);return report

def download(url,target,expected):
    temp=target.with_suffix(target.suffix+'.part')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'APK-Revival/0.2'})
        with open_url(request,timeout=45) as response,open(temp,'wb') as out:shutil.copyfileobj(response,out)
        if hashlib.sha256(temp.read_bytes()).hexdigest()!=expected:raise RevivalError('Dependency checksum did not match. The download was refused.')
        temp.replace(target)
    finally:
        if temp.exists():temp.unlink()

def install(progress=lambda _:None,root=None):
    root=pathlib.Path(root or cache_root()).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    configure(root)
    import platform
    if platform.system()!='Linux' or platform.machine() not in {'x86_64','amd64'}:raise RevivalError('The preparation-tool installer currently supports Linux x86_64. Configure tools manually for another architecture.')
    for name,(url,sha) in DOWNLOADS.items():
        progress('Downloading '+('Android build tools' if name=='buildtools.zip' else 'Android connection tools' if name=='platformtools.zip' else 'APK inspection tools'))
        target=root/name
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:download(url,target,sha)
        if name.endswith('.zip'):
            with zipfile.ZipFile(target) as z:
                for i in z.infolist():safe_member(i.filename)
                z.extractall(root)
    for name in ['aapt','aapt2','d8','apksigner','zipalign']:(root/'android-15'/name).chmod(0o755)
    (root/'platform-tools/adb').chmod(0o755)
    try:
        import re
        version=command([tool('java'),'--version'],timeout=15)
        major=re.search(r'(?:openjdk|java) (\d+)',version)
        if not major or int(major.group(1))<17:raise RevivalError('Java 17 is needed')
        tool('keytool')
    except RevivalError:
        progress('Downloading a private Java runtime')
        url='https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest'
        request=urllib.request.Request(url,headers={'User-Agent':'APK-Revival/0.2','Accept':'application/vnd.github+json'})
        with open_url(request,timeout=30) as r:metadata=json.load(r)
        packages=[a for a in metadata['assets'] if re.fullmatch(r'OpenJDK17U-jre_x64_linux_hotspot_.+\.tar\.gz',a['name'])]
        if len(packages)!=1:raise RevivalError('Could not identify the official Linux Java runtime')
        package=packages[0];link=package['browser_download_url']
        if not link.startswith('https://github.com/adoptium/temurin17-binaries/releases/download/'):raise RevivalError('Unexpected Java download origin')
        checksum_asset=next(a for a in metadata['assets'] if a['name']==package['name']+'.sha256.txt')
        with open_url(checksum_asset['browser_download_url'],timeout=30) as r:checksum=r.read().decode().split()[0]
        if not re.fullmatch('[0-9a-f]{64}',checksum):raise RevivalError('Invalid Java checksum metadata')
        target=root/'jre.tar.gz';download(link,target,checksum)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            temp=pathlib.Path(temp)
            with tarfile.open(target) as tar:
                members=tar.getmembers()
                for m in members:
                    safe_member(m.name)
                    if not (m.isfile() or m.isdir() or m.issym() or m.islnk()):raise RevivalError('Unsupported Java archive member')
                    if m.issym() or m.islnk():
                        if m.linkname.startswith('/'):raise RevivalError('Unsafe Java link')
                        dest=(temp/m.name).parent/m.linkname
                        if temp.resolve() not in dest.resolve().parents:raise RevivalError('Java link escapes extraction directory')
                tar.extractall(temp,filter='data')
            dirs=[x for x in temp.iterdir() if x.is_dir()]
            if len(dirs)!=1:raise RevivalError('Unexpected Java archive layout')
            if (root/'jre').exists():shutil.rmtree(root/'jre')
            shutil.move(dirs[0],root/'jre')
        atomic_json(root/'java-download.json',{'origin':link,'sha256':checksum})
    configure(root);progress('Checking installed tools')
    command([tool('java'),'-version'],timeout=15);command([tool('apksigner'),'version'],timeout=15)
    return health(root)

