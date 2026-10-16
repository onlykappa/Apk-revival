from __future__ import annotations
import hashlib,json,pathlib,plistlib,struct,sys,zipfile
from ..util import RevivalError,atomic_json,digest
from . import camera, timer_mod
ORIGINAL_SHA='030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2'
PACKAGE='ata.apkrv.meego'

class MeegoAdapter:
    name='meego-1.32';supported_paths=('local_backend',)
    def feasibility(self,p):return {'feasible':False,'implemented':False,'reason':'The original client and bundled assets are recoverable; a separate rebuild is not justified or implemented.'}
    def plan(self,store,p,path):
        if p['apk_sha256']!=ORIGINAL_SHA:raise RevivalError('Meego adapter requires the exact reviewed original v1.32 APK')
        if path!='local_backend':raise RevivalError('Meego currently supports the local backend path only. Standalone APK patch and rebuild workflows are not implemented for this game.')
        port=p['runtime']['backend_port'];endpoint=f'127.0.0.1:{port}'
        operations=[]
        with zipfile.ZipFile(store.base(p)) as z:
            raw=z.read('lib/armeabi/libverde.so');patches=[]
            for offset,old,new,reason in [(0x8e32f0,0xe1a05003,0xe3a05000,'Use HTTP for the local responder'),(0x8e330c,0xe59b8008,0xe3a08001,'Keep the explicit local port')]:
                if struct.unpack_from('<I',raw,offset)[0]!=old:raise RevivalError('Native patch precondition does not match Meego v1.32')
                patches.append({'offset':offset,'old':struct.pack('<I',old).hex(),'new':struct.pack('<I',new).hex(),'reason':reason})
            patches.extend(camera.patches(raw,p['runtime'].get('meego_timer_hz',60)))
            patches.extend(timer_mod.native_patches(raw))
            operations.append(self.bytes_op('lib/armeabi/libverde.so',raw,patches))
            timer_mod.patched_panel(z.read(timer_mod.ASSET))  # Validate the exact original before planning.
            operations.append(dict(type='meego_timer_panel',file=timer_mod.ASSET,
                expected_sha256=timer_mod.ASSET_SHA,revision=timer_mod.REVISION))
            for name,old,new in [('AndroidManifest.xml','ata.squid.meego',PACKAGE),('resources.arsc','Meego\0','Reviv\0')]:
                raw=z.read(name);patches=[]
                for encoding in ['utf-8','utf-16le']:
                    a,b=old.encode(encoding),new.encode(encoding);start=0
                    while True:
                        offset=raw.find(a,start)
                        if offset<0:break
                        patches.append({'offset':offset,'old':a.hex(),'new':b.hex(),'reason':'Separate installation preserves the existing original and earlier offline apps'});start=offset+len(a)
                if not patches:raise RevivalError('Compiled package/label precondition missing')
                operations.append(self.bytes_op(name,raw,patches))
            raw=z.read('assets/Info.plist');info=plistlib.loads(raw)
            for key in ['ServerURL','SecureServerURL','MediaURL']:info[key]=endpoint
            for key in ['CFBundleIdentifier','OAuthClientID']:info[key]=PACKAGE
            operations.append({'type':'replace_text_file','file':'assets/Info.plist','expected_sha256':hashlib.sha256(raw).hexdigest(),'content':plistlib.dumps(info,fmt=plistlib.FMT_XML,sort_keys=False).decode(),'reason':'Route known client services through verified ADB reverse to the host loopback responder'})
        return {'schema_version':1,'adapter':self.name,'apk_sha256':p['apk_sha256'],'apk_version':p['apk_version'],'path':path,'client_package':PACKAGE,'operations':operations,'meego_client_fixes':camera.configuration(p['runtime'].get('meego_timer_hz',60)),'backend':{'protocol':self.name,'port':port,'evidence':'docs/MEEGO.md; earlier reviewed local responder and Meego diagnostics','assumptions':['Single-player local simulation, not recovered server code','Construction/gathering/aging use documented provisional local rates','Payments and unsupported social/quest features are not reconstructed']},'asset_requirements':['Bundled TechTree.plist rules extracted into the private working copy'],'save_locations':['host saves/village.json'],'assumptions':['Earlier Deck observations do not verify this newly signed client or its ADB-reverse transport']}
    @staticmethod
    def bytes_op(name,raw,patches):return {'type':'patch_bytes','file':name,'expected_sha256':hashlib.sha256(raw).hexdigest(),'patches':patches}
    def prepare_data(self,store,p,work):
        root=work/'meego-data';root.mkdir()
        with zipfile.ZipFile(store.base(p)) as z:tree=plistlib.loads(z.read('assets/TechTree.plist'))['techtree']
        atomic_json(root/'local-rules.json',{k:tree[k] for k in ['buildings','items','jobs','points_store','birthsigns','achievements','client_data','dungeon_types','dungeon_stages']})
        resource=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[2]))/'resources/meego-starter.json'
        seed=json.loads(resource.read_text());seed['host_ip_address']='127.0.0.1';seed['media_domain']=f'127.0.0.1:{p["runtime"]["backend_port"]}';atomic_json(root/'starter-packet.json',seed)
        saved=store.directory(p['id'])/'saves/village.json'
        sources=[i for i in p['inputs'] if i['role']=='save']
        if len(sources)>1:raise RevivalError('Choose one Meego village save to import')
        if sources and not saved.exists():
            from ..saves import validate_meego_save
            state=json.loads((store.directory(p['id'])/'originals'/sources[0]['stored_name']).read_text());validate_meego_save(state);atomic_json(saved,state)
            p['logs'].append({'message':'Imported the explicitly supplied Meego village save into the separate launcher data location.'})
        return {'directory':str(root.relative_to(store.directory(p['id']))),'files':{f.name:digest(f) for f in root.iterdir()}}

