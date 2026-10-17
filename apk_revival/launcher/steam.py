"""Preserve Steam's binary shortcut records; register only while Steam is closed."""
import pathlib,struct,zlib,os,time
from ..util import RevivalError

def parse(data):
    position=0
    def entries():
        nonlocal position
        result=[]
        while position<len(data):
            kind=data[position];position+=1
            if kind==8:return result
            end=data.index(b'\0',position);name=data[position:end];position=end+1
            if kind==0:value=entries()
            elif kind==1:
                end=data.index(b'\0',position);value=data[position:end];position=end+1
            elif kind in (2,3,4,6):value=data[position:position+4];position+=4
            elif kind in (7,10):value=data[position:position+8];position+=8
            elif kind==11:value=data[position:position+1];position+=1
            else:raise RevivalError('Unsupported Steam shortcut field type '+str(kind)+'. Steam library was not changed.')
            result.append((kind,name,value))
        raise RevivalError('Truncated Steam shortcuts file; library was not changed.')
    result=entries()
    if position!=len(data):raise RevivalError('Unexpected Steam shortcut trailing data; library was not changed.')
    return result

def encode(entries):
    return b''.join(bytes([kind])+name+b'\0'+(encode(value) if kind==0 else value+b'\0' if kind==1 else value) for kind,name,value in entries)+b'\x08'

def register(executable,home=None,name='APK Revival',launch_options='--fullscreen',icon=''):
    """Add one non-Steam shortcut: the library app, or a single game via --play."""
    home=pathlib.Path(home or pathlib.Path.home())
    pidfile=home/'.steam/steam.pid'
    if pidfile.exists():
        try:
            pid=int(pidfile.read_text().strip());os.kill(pid,0)
            return {'registered':False,'reason':'Steam is running. Close Steam completely, then select Add to Steam again. Otherwise Steam overwrites the new entry when it exits.'}
        except ProcessLookupError:pass
        except (ValueError,OSError):return {'registered':False,'reason':'Steam status could not be confirmed. Close Steam and retry Add to Steam.'}
    configs=sorted((home/'.local/share/Steam/userdata').glob('*/config'))
    if len(configs)!=1:return {'registered':False,'reason':'Choose APK Revival in Steam > Games > Add a Non-Steam Game. Multiple or missing Steam profiles prevent automatic registration.'}
    path=configs[0]/'shortcuts.vdf';original=path.read_bytes() if path.exists() else b'\0shortcuts\0\x08\x08'
    records=parse(original);root=next((entry for entry in records if entry[0]==0 and entry[1]==b'shortcuts'),None)
    if root is None:raise RevivalError('Steam shortcuts root was not found.')
    def field(entry,key):return next((value for typ,label,value in entry if label.lower()==key),None)
    for kind,index,entry in root[2]:
        if kind!=0:continue
        if launch_options=='--fullscreen' and field(entry,b'appname')==name.encode():return {'registered':True,'already_present':True}
        if launch_options!='--fullscreen' and field(entry,b'launchoptions')==launch_options.encode():return {'registered':True,'already_present':True}
    exe='"'+str(executable)+'"';app_id=zlib.crc32((exe+name+('' if launch_options=='--fullscreen' else launch_options)).encode())|0x80000000
    def string(name,value):return (1,name.encode(),str(value).encode())
    def integer(name,value):return (2,name.encode(),struct.pack('<I',value))
    shortcut=[integer('appid',app_id),string('AppName',name),string('Exe',exe),string('StartDir','"'+str(pathlib.Path(executable).parent)+'"'),string('icon',icon),string('ShortcutPath',''),string('LaunchOptions',launch_options),integer('IsHidden',0),integer('AllowDesktopConfig',1),integer('AllowOverlay',1),integer('OpenVR',0),integer('Devkit',0),string('DevkitGameID',''),integer('DevkitOverrideAppID',0),integer('LastPlayTime',0),(0,b'tags',[string('0','Android')])]
    used={int(index) for kind,index,value in root[2] if index.isdigit()};index=0
    while index in used:index+=1
    root[2].append((0,str(index).encode(),shortcut))
    backup=path.with_name('shortcuts.vdf.apkr-backup-'+str(time.time_ns()))
    if path.exists():backup.write_bytes(original)
    temporary=path.with_name('shortcuts.vdf.apkr-new');temporary.write_bytes(encode(records));os.replace(temporary,path)
    return {'registered':True,'appid':app_id,'backup':str(backup)}
