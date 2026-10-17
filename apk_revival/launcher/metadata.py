"""Library metadata and artwork read from the imported original APK.

Read-only: the original APK is never modified. Icons are cached per game.
"""
from __future__ import annotations
import datetime,re,struct,zipfile

ANDROID_RELEASES={1:'1.0',2:'1.1',3:'1.5',4:'1.6',5:'2.0',6:'2.0.1',7:'2.1',8:'2.2',9:'2.3',10:'2.3.3',11:'3.0',12:'3.1',13:'3.2',14:'4.0',15:'4.0.3',16:'4.1',17:'4.2',18:'4.3',19:'4.4',20:'4.4W',21:'5.0',22:'5.1',23:'6.0',24:'7.0',25:'7.1',26:'8.0',27:'8.1',28:'9',29:'10',30:'11',31:'12',32:'12L',33:'13',34:'14',35:'15',36:'16'}
DENSITIES={'ldpi':120,'mdpi':160,'tvdpi':213,'hdpi':240,'xhdpi':320,'xxhdpi':480,'xxxhdpi':640}
IMAGE_TYPES=('.png','.webp','.jpg','.jpeg')
MAX_ICON=2*1024**2

def _length(data,p,utf8):
    first=data[p] if utf8 else struct.unpack_from('<H',data,p)[0];p+=1 if utf8 else 2
    mask=0x80 if utf8 else 0x8000
    if first&mask:
        second=data[p] if utf8 else struct.unpack_from('<H',data,p)[0];p+=1 if utf8 else 2
        return ((first&~mask)<<(8 if utf8 else 16))|second,p
    return first,p

def _pool(data,pos):
    header,size=struct.unpack_from('<HI',data,pos+2);count,_,flags,start=struct.unpack_from('<IIII',data,pos+8);utf8=bool(flags&0x100);start+=pos
    def get(index):
        if index>=count or pos+header+index*4+4>pos+size:return None
        p=start+struct.unpack_from('<I',data,pos+header+index*4)[0]
        if utf8:_,p=_length(data,p,True)
        n,p=_length(data,p,utf8)
        return data[p:p+n*(1 if utf8 else 2)].decode('utf-8' if utf8 else 'utf-16le',errors='replace')
    return get

def resource_values(arsc,resid):
    """Every configured string value of a resource ID as (density, has_locale, text)."""
    u16=lambda p:struct.unpack_from('<H',arsc,p)[0];u32=lambda p:struct.unpack_from('<I',arsc,p)[0]
    package,kind_id,entry=resid>>24,(resid>>16)&0xff,resid&0xffff
    if len(arsc)<12 or u16(0)!=2:return []
    pos=u16(2);strings=None;values=[]
    while pos+8<=len(arsc):
        kind,header,size=struct.unpack_from('<HHI',arsc,pos)
        if size<8 or pos+size>len(arsc):break
        if kind==1 and strings is None:strings=_pool(arsc,pos)
        elif kind==0x200 and u32(pos+8)==package and strings:
            child=pos+header
            while child+8<=pos+size:
                ckind,cheader,csize=struct.unpack_from('<HHI',arsc,child)
                if csize<8 or child+csize>pos+size:break
                if ckind==0x201 and arsc[child+8]==kind_id:
                    flags=arsc[child+9];count=u32(child+12);entries=child+u32(child+16);config=child+20
                    density=u16(config+14);has_locale=bool(u32(config+8));offset=None;table=child+cheader
                    if flags&1:
                        for n in range(count):
                            if u16(table+n*4)==entry:offset=u16(table+n*4+2)*4;break
                    elif entry<count:
                        raw=u16(table+entry*2) if flags&2 else u32(table+entry*4)
                        if raw not in (0xffff,0xffffffff):offset=raw*4 if flags&2 else raw
                    if offset is not None and entries+offset+8<=child+csize:
                        e=entries+offset;esize,eflags=u16(e),u16(e+2)
                        if eflags&8:dtype,data=eflags>>8,u32(e+4)
                        elif not eflags&1:dtype,data=arsc[e+esize+3],u32(e+esize+4)
                        else:dtype=None
                        if dtype==3:
                            text=strings(data)
                            if text is not None:values.append((density,has_locale,text))
                child+=csize
        pos+=size
    return values

def _resid(value):
    if value and re.fullmatch(r'@0x[0-9a-f]{8}',value):return int(value[1:],16)
    return None

def _density(path):
    folder=path.split('/')[1] if path.count('/')>=2 else ''
    for name,dpi in sorted(DENSITIES.items(),key=lambda x:-len(x[0])):
        if re.search(r'-'+name+r'(-|$)',folder):return dpi
    return 160

def _heuristic_icon(names,hint=None):
    best=None
    for name in names:
        lower=name.lower()
        if not lower.startswith('res/') or not lower.endswith(IMAGE_TYPES) or not re.match(r'res/(mipmap|drawable)',lower):continue
        stem=lower.rsplit('/',1)[-1].rsplit('.',1)[0]
        if any(x in stem for x in ('foreground','background','monochrome','notification','splash','banner')):continue
        if hint and stem==hint:rank=4
        elif stem in ('ic_launcher','app_icon','icon','ic_launcher_round'):rank=3
        elif re.search(r'launcher|app_?icon',stem):rank=2
        else:continue
        score=(rank,_density(lower))
        if not best or score>best[0]:best=(score,name)
    return best[1] if best else None

def find_icon(apk,application=None):
    """Return the APK member of the best launcher icon bitmap, or None."""
    application=application or {}
    with zipfile.ZipFile(apk) as z:
        names=z.namelist();raw=application.get('icon') or application.get('roundIcon')
        resid=_resid(raw)
        if resid and 'resources.arsc' in names:
            try:
                paths=[(d,t) for d,_,t in resource_values(z.read('resources.arsc'),resid) if t.lower().endswith(IMAGE_TYPES) and t in names]
                if paths:
                    # Density 0 is the default; 0xfffe/0xffff are any/no density.
                    return max(paths,key=lambda x:x[0] if x[0]<0xfffe else 0)[1]
            except (struct.error,IndexError,UnicodeDecodeError):pass
        hint=raw.rsplit('/',1)[-1].lower() if raw and raw.startswith('@') and '/' in raw else None
        return _heuristic_icon(names,hint)

def resolve_label(apk,value):
    """Resolve a binary manifest label reference to its default text."""
    resid=_resid(value)
    if not resid:return value
    try:
        with zipfile.ZipFile(apk) as z:
            if 'resources.arsc' not in z.namelist():return None
            values=resource_values(z.read('resources.arsc'),resid)
    except (OSError,zipfile.BadZipFile,struct.error,IndexError):return None
    default=[t for _,locale,t in values if not locale and t.strip()]
    text=(default or [t for _,_,t in values if t.strip()] or [None])[0]
    return text.strip()[:100] if text else None

def icon_path(store,p):
    """Cached icon file for a game, extracted on first use. None if unavailable."""
    folder=store.directory(p['id'])/'artwork'
    for existing in folder.glob('icon.*') if folder.is_dir() else []:
        return existing if existing.suffix!='.none' else None
    try:
        application=(p.get('analysis') or {}).get('metadata',{}).get('application',{})
        apk=store.base(p);member=find_icon(apk,application)
        folder.mkdir(parents=True,exist_ok=True)
        if member:
            with zipfile.ZipFile(apk) as z:
                if z.getinfo(member).file_size<=MAX_ICON:
                    target=folder/('icon'+member[member.rfind('.'):].lower());target.write_bytes(z.read(member));return target
        (folder/'icon.none').write_text('No launcher bitmap found in the original APK.\n')
    except (OSError,StopIteration,KeyError,zipfile.BadZipFile):pass
    return None

def human_size(n):
    for unit in ['bytes','KB','MB','GB']:
        if n<1024 or unit=='GB':return (f'{n:.0f} {unit}' if unit=='bytes' else f'{n:.1f} {unit}')
        n/=1024

def friendly_date(value):
    try:
        moment=datetime.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).astimezone()
    except (TypeError,ValueError):return None
    return moment.strftime('%d %b %Y, %H:%M').lstrip('0')

def android_name(sdk):
    if not sdk or not str(sdk).isdigit():return None
    release=ANDROID_RELEASES.get(int(sdk));return ('Android '+release if release else 'API '+str(sdk))

ABI_NAMES={'arm64-v8a':'ARM 64-bit','armeabi-v7a':'ARM 32-bit','armeabi':'ARM (legacy)','x86':'x86','x86_64':'x86 64-bit','mips':'MIPS','mips64':'MIPS 64-bit'}
PATH_LABELS={'offline_patch':'Offline patch','local_backend':'Local game service','rebuild':'Separate rebuild'}

def details(p):
    """Ordered (label, value) rows for the library details pane."""
    a=p.get('analysis') or {};meta=a.get('metadata') or {};rows=[]
    version=meta.get('version_name') or (p.get('apk_version') or {}).get('name')
    if version:rows.append(('Version',str(version)+(f'  (build {meta["version_code"]})' if meta.get('version_code') else '')))
    if meta.get('package'):rows.append(('Package',meta['package']))
    if a.get('engine') and a['engine']!='Unknown':rows.append(('Engine',a['engine']))
    need=android_name(meta.get('min_sdk'))
    if need:rows.append(('Requires',need+' or newer'))
    if meta.get('target_sdk'):rows.append(('Built for',android_name(meta['target_sdk'])))
    if a:rows.append(('Architecture',', '.join(ABI_NAMES.get(x,x) for x in a.get('abis',[])) or 'Any (no native code)'))
    size=sum(i.get('size',0) for i in p.get('inputs',[]))
    extras=len([i for i in p.get('inputs',[]) if i.get('role')!='base_apk'])
    if size:rows.append(('Size',human_size(size)+(f'  ·  {extras} extra file'+('s' if extras!=1 else '') if extras else '')))
    path=(p.get('restoration') or {}).get('path')
    if path:rows.append(('Method',PATH_LABELS.get(path,path)))
    for key,label in [('created_at','Added')]:
        when=friendly_date(p.get(key))
        if when:rows.append((label,when))
    launcher=p.get('launcher') or {}
    played=friendly_date(launcher.get('last_played'))
    rows.append(('Last played',played or 'Never'))
    if launcher.get('playtime_seconds'):rows.append(('Play time',playtime(launcher['playtime_seconds'])))
    return rows

def subtitle(p):
    meta=((p.get('analysis') or {}).get('metadata') or {})
    version=meta.get('version_name')
    kind='Desktop rebuild' if (p.get('restoration') or {}).get('path')=='rebuild' else 'Android game'
    return kind+('  ·  v'+str(version) if version else '')


def playtime(seconds):
    minutes=int(seconds)//60
    if minutes<1:return 'Under a minute'
    hours,minutes=divmod(minutes,60)
    return ' '.join(part for part in (f'{hours} h' if hours else '',f'{minutes} min' if minutes else '') if part)
