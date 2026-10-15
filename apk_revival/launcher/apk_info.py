"""Read Android resource metadata with SDK aapt; keep icons in the game directory."""
import pathlib,re,zipfile
from ..util import command,tool,RevivalError

def inspect_apk(path,directory):
    try:output=command([tool('aapt'),'dump','badging',path],timeout=30)
    except RevivalError:output=''
    def value(pattern):
        match=re.search(pattern,output,re.M)
        return match.group(1) if match else None
    package=value(r"^package: name='([^']+)'")
    if not package:return manifest_info(path)
    launch=value(r"^launchable-activity: name='([^']+)'")
    title=value(r"^application-label:'([^']*)'")
    icons=re.findall(r"^application-icon-(\d+):'([^']+)'",output,re.M)
    icon=None
    with zipfile.ZipFile(path) as archive:
        for _,name in sorted(icons,key=lambda pair:int(pair[0]),reverse=True):
            if name.lower().endswith(('.png','.webp','.jpg')) and name in archive.namelist():
                data=archive.read(name)
                if len(data)<=4*1024*1024:
                    dest=pathlib.Path(directory)/('icon'+pathlib.Path(name).suffix)
                    dest.write_bytes(data);icon=str(dest);break
    return {'package':package,'launch_activity':launch,'label':title,'icon':icon,
            'abis':re.findall(r"'([^']+)'",value(r'^native-code: (.+)$') or ''),
            'min_sdk':value(r"^sdkVersion:'([^']+)'"),'target_sdk':value(r"^targetSdkVersion:'([^']+)'"),
            'icon_note':None if icon else 'Adaptive or unavailable icon; using library artwork.'}

def manifest_info(path):
    from ..analysis import manifest,binary_manifest
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as archive:
        data=archive.read('AndroidManifest.xml');metadata=manifest(data)
        if data.lstrip().startswith(b'<'):
            events=[]
            def walk(element):
                name=element.tag.split('}')[-1];events.append((name,{k.split('}')[-1]:v for k,v in element.attrib.items()}))
                for child in element:walk(child)
                events.append(('/'+name,{}))
            walk(ET.fromstring(data))
        else:events=binary_manifest(data,events=True)
        package=metadata['package'];activity=None;launch=None;main=False;launcher=False;in_filter=False
        for name,attrs in events:
            if name in ('activity','activity-alias'):activity=attrs.get('name') if attrs.get('enabled')!='false' else None
            elif name=='intent-filter':in_filter=True;main=False;launcher=False
            elif in_filter and name=='action' and attrs.get('name')=='android.intent.action.MAIN':main=True
            elif in_filter and name=='category' and attrs.get('name')=='android.intent.category.LAUNCHER':launcher=True
            elif name=='/intent-filter':
                if main and launcher and activity:launch=activity
                in_filter=False
            elif name in ('/activity','/activity-alias'):activity=None
        if not package:raise RevivalError('APK has no package name.')
        if launch and launch.startswith('.'):launch=package+launch
        elif launch and '.' not in launch:launch=package+'.'+launch
        return {'package':package,'launch_activity':launch,'label':metadata['application'].get('label'),'icon':None,
                'abis':sorted({n.split('/')[1] for n in archive.namelist() if n.startswith('lib/') and n.endswith('.so')}),
                'min_sdk':metadata['min_sdk'],'target_sdk':metadata['target_sdk'],
                'icon_note':'SDK resource reader unavailable; manifest read directly.'}
