"""Bounded APK inspection. String references are leads, never protocol proof."""
from __future__ import annotations
import re, struct, xml.etree.ElementTree as ET, zipfile
from .util import RevivalError, command, digest, inspect_zip, now, tool

ANDROID='{http://schemas.android.com/apk/res/android}'

def binary_manifest(data,events=False):
    """Read Android's little-endian ResXMLTree / ResStringPool chunks."""
    strings=[]; tags=[]; pos=8
    def u16(p):return struct.unpack_from('<H',data,p)[0]
    def u32(p):return struct.unpack_from('<I',data,p)[0]
    def string(i):return strings[i] if i!=0xffffffff and i<len(strings) else None
    def length(p,utf8):
        first=data[p] if utf8 else u16(p); p+=1 if utf8 else 2
        mask=0x80 if utf8 else 0x8000
        if first & mask:
            second=data[p] if utf8 else u16(p);p+=1 if utf8 else 2
            return ((first & ~mask)<<(7 if utf8 else 16))|second,p
        return first,p
    while pos+8<=len(data):
        kind,header,size=struct.unpack_from('<HHI',data,pos)
        if size<header or pos+size>len(data):raise RevivalError('Malformed binary manifest chunk')
        if kind==1:
            count=u32(pos+8);flags=u32(pos+16);start=pos+u32(pos+20);utf8=bool(flags&0x100)
            if count>200000 or header+count*4>size:raise RevivalError('Invalid manifest string pool')
            for n in range(count):
                p=start+u32(pos+header+n*4)
                if utf8:_,p=length(p,True)
                size_s,p=length(p,utf8)
                strings.append(data[p:p+size_s*(1 if utf8 else 2)].decode('utf-8' if utf8 else 'utf-16le',errors='replace'))
        elif kind==0x102:
            ext=pos+header;name=string(u32(ext+4));offset=u16(ext+8);attrsize=u16(ext+10);count=u16(ext+12);attrs={}
            if attrsize<20 or ext+offset+attrsize*count>pos+size:raise RevivalError('Malformed manifest attributes')
            for n in range(count):
                a=ext+offset+n*attrsize;key=string(u32(a+4));raw=string(u32(a+8));typ=data[a+15];value=u32(a+16)
                attrs[key]=raw if raw is not None else (string(value) if typ==3 else str(value) if typ in (0x10,0x11) else ('true' if value else 'false') if typ==0x12 else f'@0x{value:08x}')
            tags.append((name,attrs))
        elif kind==0x103 and events:
            tags.append(('/'+str(string(u32(pos+header+4))),{}))
        pos+=size
    if not tags:raise RevivalError('Manifest contains no readable tags')
    return tags

def manifest(data):
    try:
        if data.lstrip().startswith(b'<'):
            root=ET.fromstring(data)
            tags=[(e.tag.split('}')[-1],{k.split('}')[-1]:v for k,v in e.attrib.items()}) for e in root.iter()]
        else:tags=binary_manifest(data)
    except (ValueError,struct.error,IndexError,ET.ParseError) as e:raise RevivalError('Cannot parse Android manifest: '+str(e)) from e
    base=next((a for t,a in tags if t=='manifest'),{})
    sdk=next((a for t,a in tags if t=='uses-sdk'),{})
    return {'package':base.get('package'),'version_name':base.get('versionName'),'version_code':base.get('versionCode'),'split':base.get('split'),'min_sdk':sdk.get('minSdkVersion','1'),'target_sdk':sdk.get('targetSdkVersion'),'permissions':[a.get('name') for t,a in tags if t=='uses-permission'],'activities':[a.get('name') for t,a in tags if t=='activity'],'application':next((a for t,a in tags if t=='application'),{})}

def dex_strings(data):
    if not data.startswith(b'dex\n') or len(data)<112:return []
    count,offset=struct.unpack_from('<II',data,56)
    if count>1000000 or offset+4*count>len(data):return []
    out=[]
    for i in range(count):
        p=struct.unpack_from('<I',data,offset+4*i)[0];start=p
        for _ in range(5):
            if p>=len(data):break
            b=data[p];p+=1
            if b<128:break
        end=data.find(b'\0',p,min(len(data),p+65536))
        if end>p:out.append((start,data[p:end].decode('utf-8',errors='replace')))
    return out

def analyze(store,game_id):
    p=store.load(game_id); path=store.base(p);names=inspect_zip(path); findings=[];endpoints=[]; references=[]; errors=[]
    def finding(kind,statement,evidence,confidence='medium',classification='inferred'):
        findings.append({'kind':kind,'statement':statement,'classification':classification,'confidence':confidence,'evidence':evidence})
    with zipfile.ZipFile(path) as z:
        meta=manifest(z.read('AndroidManifest.xml'))
        if not meta['package'] or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+',meta['package']):raise RevivalError('Invalid or unavailable package name')
        if meta['split']:raise RevivalError('Selected APK is a split. Import the base APK and attach this split instead.')
        libs=[n for n in names if n.startswith('lib/') and n.endswith('.so')]
        abis=sorted({n.split('/')[1] for n in libs})
        assets=[{'path':i.filename,'size':i.file_size} for i in z.infolist() if i.filename.startswith(('assets/','res/raw/'))]
        engine='Unknown'
        for engine_name,pattern in [('Unity',r'libunity\.so|assets/bin/Data/'),('Unreal',r'libUE4\.so|libUnreal\.so|\.pak$'),('Cocos2d',r'libcocos|cocos2d'),('Godot',r'libgodot|\.pck$')]:
            hits=[n for n in names if re.search(pattern,n,re.I)]
            if hits:engine=engine_name;finding('engine',engine_name+' signature found',hits,'high');break
        fixture=False
        if meta['package']=='org.apkrevival.tapquest' and 'assets/revival.json' in names:
            import json
            try:
                c=json.loads(z.read('assets/revival.json'));fixture=c.get('fixture')=='tapquest-v1'
            except (ValueError,KeyError):pass
        if fixture:
            p['adapter']='tapquest-v1';engine='Android native (self-authored fixture)'
            finding('fixture','Self-authored Tap Quest adapter marker, not a commercial restoration',['assets/revival.json'],'high','discovered')
        else:
            # Game plugins recognise the exact games they support.
            from .adapters import ADAPTERS
            p['adapter']=next((a.name for a in list(ADAPTERS.values()) if hasattr(a,'detect') and a.detect(p,z,finding,endpoints)),None)
        for name in names:
            if name.endswith('.dex'):
                candidates=dex_strings(z.read(name))
            elif name.startswith('assets/') and z.getinfo(name).file_size<2*1024**2 and name.lower().endswith(('.json','.xml','.txt','.js','.html','.cfg','.ini','.properties')):
                candidates=[(0,z.read(name).decode('utf-8',errors='replace'))]
            else:continue
            for offset,s in candidates:
                evidence=f'{name}:byte@{offset}'
                for match in re.finditer(r'https?://[^\s"\x00<>\\]+',s):
                    url=match.group(0).rstrip("',);}")[:500]
                    if len(endpoints)<2000 and not any(x['url']==url and x['evidence']==evidence for x in endpoints):endpoints.append({'url':url,'evidence':evidence,'classification':'discovered reference, behavior unproven'})
                for category,pattern in [('authentication',r'login|oauth|auth/token|authenticate'),('configuration',r'remoteconfig|/config|config_url'),('downloads',r'assetbundle|\.obb\b|\bdownload\b|^/(?:content|assets)(?:/|$)|https?://[^\s]+/(?:content|assets)(?:/|$)'),('progression',r'leaderboard|/progress|/action|/state'),('saves',r'SharedPreferences|SQLite|savegame|savedata|getFilesDir')]:
                    if re.search(pattern,s,re.I) and len(references)<2000:references.append({'category':category,'excerpt':s[:160],'evidence':evidence})
        supporting_inventory=[{'name':i['name'],'role':i['role'],'size':i['size'],'sha256':i['sha256'],'relative_path':i.get('relative_path')} for i in p['inputs'] if i['role']!='base_apk']
        supplied_log_observations=[]
        for i in p['inputs']:
            if i['role']!='log' or i['size']>8*1024**2:continue
            content=(store.directory(game_id)/'originals'/i['stored_name']).read_text(encoding='utf-8',errors='replace')
            for number,line in enumerate(content.splitlines(),1):
                if re.search(r'FATAL EXCEPTION|UnknownHostException|ConnectException|SSLHandshakeException|missing.*asset|FileNotFoundException',line,re.I) and len(supplied_log_observations)<100:
                    supplied_log_observations.append({'excerpt':line[:300],'evidence':f'originals/{i["stored_name"]}:line@{number}','classification':'user-supplied log observation; capture context unverified'})
        if supplied_log_observations:finding('runtime_log','Supplied logs contain runtime failure observations. These are leads, not a complete protocol or verified offline behavior.',[x['evidence'] for x in supplied_log_observations[:12]],'medium','discovered')
        if any(i['role']=='obb' for i in p['inputs']):finding('assets','OBB supporting files supplied. Their required placement is known by package; completeness/content consistency still needs runtime testing.',[i['name'] for i in p['inputs'] if i['role']=='obb'],'high','discovered')
        splits=[]
        for i in p['inputs']:
            if i['role']=='split_apk':
                with zipfile.ZipFile(store.directory(game_id)/'originals'/i['stored_name']) as split:
                    sm=manifest(split.read('AndroidManifest.xml'))
                    if sm['package']!=meta['package'] or sm['version_code']!=meta['version_code']:errors.append('Split package/version mismatch: '+i['name'])
                    split_libs=[n for n in split.namelist() if n.startswith('lib/') and n.endswith('.so')]
                    abis=sorted(set(abis)|{n.split('/')[1] for n in split_libs})
                    libs.extend(i['name']+'::'+n for n in split_libs)
                    splits.append({'name':i['name'],'metadata':sm})
        if endpoints:finding('network','Network endpoint references found. Request schemas and required responses are unknown without runtime/source evidence.',[x['evidence'] for x in endpoints[:12]],'high','discovered')
        if any(x['category']=='saves' for x in references):finding('save','Local save API references exist; whether gameplay uses them needs runtime confirmation',[x['evidence'] for x in references if x['category']=='saves'][:12])
        if not assets:finding('assets','No assets/ or res/raw/ entries. This does not prove assets are missing.',['ZIP inventory'],'low')
        if any(x['category']=='downloads' for x in references) and not any(x['role']=='obb' for x in p['inputs']):finding('assets','Download/expansion references may indicate required external content. No OBB was supplied.',[x['evidence'] for x in references if x['category']=='downloads'][:12],'low')
        if abis and not any(a in abis for a in ['x86','x86_64']):finding('compatibility','Native libraries lack x86 variants. Steam Deck Waydroid may require separately configured ARM translation.',libs,'high','discovered')
    from .adapters import find
    plugin=find(p) if not fixture else None
    recommendation=getattr(plugin,'recommended_path',None) or ('offline_patch' if fixture else ('local_backend' if endpoints else 'offline_patch'))
    obstacles=errors+(['No game-specific restoration adapter. Analysis cannot reconstruct a server automatically.'] if not p.get('adapter') else [])
    obstacles += ['No runtime observation yet. Original gameplay and offline behavior remain unverified.']
    report={'generated_at':now(),'metadata':meta,'abis':abis,'engine':engine,'fixture':fixture,'assets':assets,'native_libraries':libs,'splits':splits,'supporting_inventory':supporting_inventory,'supplied_log_observations':supplied_log_observations,'endpoints':endpoints,'references':references,'findings':findings,'obstacles':obstacles,'input_errors':errors,'recommended_path':recommendation,'recommendation_confidence':'high' if fixture else 'medium' if p.get('adapter') else 'low','recommendation_reason':'Fixture has an explicit local-mode branch in included source.' if fixture else getattr(plugin,'recommendation_reason','A reviewed game adapter supports this exact game.') if p.get('adapter') else 'Provisional triage from references only; collect runtime evidence before choosing a repair.','alternatives':[{'path':x,'reason':'Preserve gameplay with the smallest evidence-supported change.' if x=='offline_patch' else 'Recover a documented local protocol and persistent progression.' if x=='local_backend' else 'Last resort: independently implement recoverable mechanics and permitted assets.'} for x in ['offline_patch','local_backend','rebuild'] if x!=recommendation],'next_steps':['Run doctor and configure one Waydroid ADB serial.','Capture a cold launch log and identify the first failing gameplay request.','Supply missing expansion/assets and known request/response samples.','Review an adapter plan before modifying any copy.']}
    p['analysis']=report;p['apk_version']={'name':meta['version_name'],'code':meta['version_code']};p['status']='Analyzed' if p.get('adapter') else 'Needs Evidence';p['verification']=[];store.save(p)
    d=store.directory(game_id);from .util import atomic_json
    atomic_json(d/'analysis.json',report);(d/'analysis.md').write_text(markdown(p),encoding='utf-8');return p

def markdown(p):
    a=p['analysis']; m=a['metadata']; out=[f'# APK Revival analysis: {p["title"]}',f'\nAPK SHA-256: `{p["apk_sha256"]}`',f'\nStatus: **{p["status"]}**',f'\nPackage: `{m["package"]}` | Version: {m["version_name"]} ({m["version_code"]})',f'\nAndroid min/target: {m["min_sdk"]}/{m["target_sdk"]} | ABIs: {", ".join(a["abis"]) or "no bundled native libraries"}',f'\nEngine: {a["engine"]}',f'\nRecommended: **{a["recommended_path"]}**, confidence {a["recommendation_confidence"]}. {a["recommendation_reason"]}', '\n## Evidence']
    for f in a['findings']:out.append(f'\n* [{f["classification"]}, {f["confidence"]}] {f["statement"]} Evidence: '+', '.join('`'+s+'`' for s in f['evidence']))
    out += ['\n## Endpoint references (not observed server behavior)']
    out += [f'\n* `{x["url"]}` from `{x["evidence"]}`' for x in a['endpoints']]
    out += ['\n## Obstacles']+['\n* '+x for x in a['obstacles']]
    out += ['\n## Next steps']+['\n* '+x for x in a['next_steps']]
    out += ['\n## Alternatives']+['\n* '+x['path']+': '+x['reason'] for x in a['alternatives']]
    out += ['\nFull asset, permission, split and reference inventory: analysis.json. Static inspection is not proof of gameplay.']
    return '\n'.join(out)+'\n'

