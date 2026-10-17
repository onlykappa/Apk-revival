from __future__ import annotations
import json, os, pathlib, re, shutil, uuid
from .util import RevivalError, atomic_json, digest, inspect_zip, now, read_json, safe_member

STATUSES={'Imported','Analyzed','Needs Evidence','Restoration In Progress','Exported but Unverified','Verified Offline'}

class Store:
    def __init__(self, root=None):
        self.root=pathlib.Path(root or os.getenv('APKR_DATA', pathlib.Path.home()/'.local/share/apk-revival')).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.last_library_errors=[]
    def directory(self, game_id):
        if not game_id or len(game_id)!=24 or any(c not in '0123456789abcdef' for c in game_id):raise RevivalError('Invalid game ID')
        return self.root/'games'/game_id
    def load(self, game_id, check=True):
        d=self.directory(game_id); p=read_json(d/'profile.json')
        if not isinstance(p,dict) or p.get('schema_version')!=1 or p.get('id')!=game_id:raise RevivalError('Unsupported or inconsistent profile')
        if check:
            for i in p['inputs']:
                if digest(d/'originals'/i['stored_name'])!=i['sha256']:raise RevivalError('Original input hash changed. Restore original or import a new version.')
        return p
    def save(self, p):
        if p['status'] not in STATUSES:raise RevivalError('Unknown status')
        d=self.directory(p['id']); history=d/'history'; history.mkdir(exist_ok=True)
        p['updated_at']=now(); p['revision']=p.get('revision',0)+1
        atomic_json(history/f'{p["revision"]:06d}.json',p)
        atomic_json(d/'profile.json',p)
    def games(self):
        # A damaged entry must not prevent healthy games from being displayed.
        # Report rather than rewrite the original evidence or profile/history.
        self.last_library_errors=[]; profiles=[]
        directory=self.root/'games'
        try:entries=sorted(directory.iterdir())
        except FileNotFoundError:return profiles
        except OSError as e:
            self.last_library_errors.append({'file':str(directory),'error':str(e)[:500]});return profiles
        for entry in entries:
            if not entry.is_dir():continue
            path=entry/'profile.json'
            try:
                profile=read_json(path)
                self._validate_library_profile(profile,entry.name)
            except (OSError,UnicodeError,json.JSONDecodeError,RecursionError,RevivalError) as e:
                self.last_library_errors.append({'file':str(path),'error':str(e)[:500]})
                continue
            profiles.append(profile)
        return profiles
    def _validate_library_profile(self,p,game_id):
        """Validate structures used by library/details without hashing APKs.

        Store.load retains its existing original-input hash verification. This
        listing check never alters a file or fills in an invented replacement.
        """
        self.directory(game_id)
        if not isinstance(p,dict):raise RevivalError('Profile must be a JSON object')
        if type(p.get('schema_version')) is not int or p['schema_version']!=1 or p.get('id')!=game_id:
            raise RevivalError('Unsupported or inconsistent profile')
        if not isinstance(p.get('title'),str) or not p['title'].strip():raise RevivalError('Profile title must be nonempty text')
        if not isinstance(p.get('status'),str) or p['status'] not in STATUSES:raise RevivalError('Unknown profile status')
        inputs=p.get('inputs')
        if not isinstance(inputs,list) or not inputs:raise RevivalError('Profile inputs must be a nonempty list')
        for item in inputs:
            if not isinstance(item,dict):raise RevivalError('Profile input must be an object')
            for key in ('name','stored_name','role'):
                if not isinstance(item.get(key),str) or not item[key]:raise RevivalError('Invalid profile input '+key)
            stored=item['stored_name']
            if pathlib.PurePosixPath(stored).name!=stored or '\\' in stored or stored in ('.','..'):
                raise RevivalError('Invalid stored input filename')
            sha=item.get('sha256')
            if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
                raise RevivalError('Invalid profile input SHA256')
            if type(item.get('size')) is not int or item['size']<0:raise RevivalError('Invalid profile input size')
        if sum(item['role']=='base_apk' for item in inputs)!=1:raise RevivalError('Profile must identify one base APK')
        restoration=p.get('restoration')
        if not isinstance(restoration,dict) or 'path' not in restoration:raise RevivalError('Invalid restoration profile')
        for key in ('path','artifact'):
            if restoration.get(key) is not None and not isinstance(restoration[key],str):raise RevivalError('Invalid restoration '+key)
        if 'analysis' not in p:raise RevivalError('Missing analysis profile field')
        analysis=p['analysis']
        if analysis is not None and not isinstance(analysis,dict):raise RevivalError('Invalid analysis profile')
        if analysis and (not isinstance(analysis.get('fixture'),bool) or not isinstance(analysis.get('recommended_path'),str)):
            raise RevivalError('Invalid analysis library fields')
        for key in ('runtime','rebuild','launcher'):
            if key in p and not isinstance(p[key],dict):raise RevivalError('Invalid '+key+' profile')
        launcher=p.get('launcher',{})
        if 'apk' in launcher and not isinstance(launcher['apk'],dict):raise RevivalError('Invalid APK launcher metadata')
        icon=launcher.get('apk',{}).get('icon')
        if icon is not None and not isinstance(icon,str):raise RevivalError('Invalid APK icon path')
        if 'verification' not in p:raise RevivalError('Missing verification profile field')
        for value,name in [(p.get('verification',[]),'verification'),(launcher.get('launch_checks',[]),'launch checks')]:
            if not isinstance(value,list) or any(not isinstance(item,dict) for item in value):raise RevivalError('Invalid '+name+' list')
    def import_game(self, apk, supporting=()):
        apk=pathlib.Path(apk).resolve()
        from .bundles import is_bundle,unpack
        if is_bundle(apk):
            # XAPK/APKS/APKM: import the base APK with its own splits and OBBs.
            staged=self.root/('bundle-'+uuid.uuid4().hex)
            try:
                parts=unpack(apk,staged);base=parts['base']
                existing=self.directory(digest(base)[:24])
                if existing.exists():return self.import_game(base)
                p=self.import_game(base,[*parts['splits'],*parts['obbs'],*supporting])
                # Bundles usually call the base file base.apk; prefer the bundle's name.
                if p['title']==base.stem:p['title']=apk.stem[:100];self.save(p)
                return p
            finally:shutil.rmtree(staged,ignore_errors=True)
        if apk.suffix.lower()!='.apk':raise RevivalError('Choose an .apk, .xapk, .apks or .apkm file.')
        names=inspect_zip(apk)
        if 'AndroidManifest.xml' not in names or not any(n.startswith('classes') and n.endswith('.dex') for n in names):
            raise RevivalError('Not an executable APK: manifest and DEX are required')
        h=digest(apk); game_id=h[:24]; target=self.directory(game_id)
        if target.exists():
            p=self.load(game_id)
            if p['apk_sha256']!=h:raise RevivalError('Hash ID collision')
            if supporting:raise RevivalError('Already imported. To add evidence, use attach rather than replacing originals.')
            return p
        staged=self.root/('import-'+uuid.uuid4().hex); (staged/'originals').mkdir(parents=True)
        try:
            inputs=[]
            self._copy_input(apk,'base_apk',staged,inputs)
            for s in supporting:
                role,source=s if isinstance(s,tuple) else (None,s)
                self._add_source(pathlib.Path(source).resolve(),staged,inputs,role)
            p={'schema_version':1,'id':game_id,'title':apk.stem,'apk_sha256':h,'apk_version':None,'created_at':now(),'status':'Imported','inputs':inputs,'analysis':None,'adapter':None,'restoration':{'path':None,'operations':[],'artifact':None},'runtime':{'adapter':'waydroid','serial':None,'backend_port':18765},'verification':[],'rebuild':{'status':'Not Started','feasibility':None},'logs':[]}
            target.parent.mkdir(parents=True,exist_ok=True); staged.rename(target); self.save(p); return p
        finally:
            if staged.exists():shutil.rmtree(staged)
    def _copy_input(self, source, role, d, inputs):
        if not source.is_file() or source.is_symlink():raise RevivalError('Input must be a regular non-symlink file')
        ext=source.suffix.lower(); allowed={'.apk','.obb','.log','.txt','.json','.sav','.dat','.bin','.db','.sqlite','.png','.jpg','.jpeg','.webp','.wav','.ogg','.mp3','.unity3d','.bundle','.xml','.pak','.pck','.ktx','.ktx2','.ttf','.otf','.webm','.mp4','.csv'}
        if ext not in allowed:raise RevivalError('Unsupported supporting format: '+ext)
        if ext=='.apk':inspect_zip(source)
        h=digest(source); stored=f'{len(inputs):04d}_{source.name}'
        shutil.copyfile(source,d/'originals'/stored)
        if digest(d/'originals'/stored)!=h:raise RevivalError('Input changed while copying')
        os.chmod(d/'originals'/stored,0o400)
        inputs.append({'name':source.name,'stored_name':stored,'role':role,'sha256':h,'size':source.stat().st_size})
    def _add_source(self, source, d, inputs, role_override=None):
        if role_override not in {None,'asset','save','log'}:raise RevivalError('Unsupported input role')
        if source.is_dir():
            for p in sorted(source.rglob('*')):
                if p.is_symlink():raise RevivalError('Supporting asset symlinks are unsupported')
                if p.is_file():
                    self._copy_input(p,role_override or 'asset',d,inputs)
                    inputs[-1]['relative_path']=source.name+'/'+str(p.relative_to(source))
        else:
            role={'.apk':'split_apk','.obb':'obb','.log':'log','.txt':'log','.sav':'save','.db':'save','.sqlite':'save','.dat':'save','.bin':'save','.json':'evidence','.xml':'evidence'}.get(source.suffix.lower(),'asset')
            role=role_override or role
            self._copy_input(source,role,d,inputs)
    def attach(self, game_id, sources):
        p=self.load(game_id); d=self.directory(game_id)
        staged=self.root/('attach-'+uuid.uuid4().hex); (staged/'originals').mkdir(parents=True)
        new=[]
        try:
            for source in sources:
                role,value=source if isinstance(source,tuple) else (None,source)
                self._add_source(pathlib.Path(value).resolve(),staged,new,role)
            for i in new:
                original=i['stored_name']; i['stored_name']=f'{len(p["inputs"]):04d}_{i["name"]}'
                shutil.move(staged/'originals'/original,d/'originals'/i['stored_name']); p['inputs'].append(i)
            p['status']='Imported'; p['analysis']=None; p['verification']=[]; p['restoration']={'path':None,'operations':[],'artifact':None}; self.save(p); return p
        finally:shutil.rmtree(staged)
    def remove(self,game_id):
        """Delete a library entry but keep its saves and backups in removed-games/."""
        p=self.load(game_id,check=False);d=self.directory(game_id);kept=None
        keep=[d/name for name in ('saves','backups') if (d/name).is_dir() and any((d/name).iterdir())]
        if keep:
            title=re.sub(r'[^A-Za-z0-9._-]+','-',p.get('title') or 'game').strip('-')[:40] or 'game'
            kept=self.root/'removed-games'/f'{title}-{game_id[:8]}-{now().replace(":","-")}'
            kept.mkdir(parents=True)
            for folder in keep:shutil.move(str(folder),str(kept/folder.name))
            atomic_json(kept/'removed.json',{'id':game_id,'title':p.get('title'),'package':((p.get('analysis') or {}).get('metadata') or {}).get('package'),'apk_sha256':p.get('apk_sha256'),'removed_at':now()})
        shutil.rmtree(d);return str(kept) if kept else None
    def base(self,p):
        return self.directory(p['id'])/'originals'/next(i['stored_name'] for i in p['inputs'] if i['role']=='base_apk')
    def log(self,p,message):
        p['logs'].append({'time':now(),'message':message});self.save(p)
    def reset(self,game_id):
        p=self.load(game_id)
        p['restoration']={'path':None,'operations':[],'artifact':None}; p['verification']=[];p['status']='Analyzed' if p['analysis'] else 'Imported'
        # Preserve working versions for review rather than delete files.
        self.save(p);return p

