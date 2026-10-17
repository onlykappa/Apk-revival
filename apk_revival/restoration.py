from __future__ import annotations
import difflib, hashlib, json, os, pathlib, secrets, shutil, uuid, zipfile
from .adapters import PATHS, adapter
from .util import RevivalError, apktool, atomic_json, command, digest, read_json, safe_member, tool

class Restorer:
    def __init__(self,store):self.store=store
    def plan(self,game_id,path):
        p=self.store.load(game_id)
        if not p['analysis']:raise RevivalError('Analyze first')
        if p['analysis']['input_errors']:raise RevivalError('Resolve split input mismatches first')
        plan=adapter(p).plan(self.store,p,path)
        atomic_json(self.store.directory(game_id)/f'plan-{path}.json',plan);return plan
    def prepare(self,game_id,path,plan_path=None,progress=None):
        progress=progress or (lambda _:None)
        progress("Checking game files")
        p=self.store.load(game_id)
        if not p['analysis']:raise RevivalError('Analyze first')
        if path not in PATHS:raise RevivalError('Unsupported restoration path')
        plan=read_json(plan_path) if plan_path else self.plan(game_id,path)
        self._validate(p,plan,path)
        if path=='rebuild':
            progress('Checking rebuild feasibility')
            feasible=adapter(p).feasibility(p)
            if not feasible.get('feasible'):raise RevivalError('Rebuild feasibility not established')
            p['rebuild']={'status':'Implemented fixture rebuild; GUI gameplay unverified','feasibility':feasible,'save_location':'saves/rebuild.json'}
            p['restoration']={'path':path,'operations':[],'artifact':None,'plan':plan};p['status']='Restoration In Progress';p['verification']=[];self.store.save(p);return p
        if any(i['role']=='split_apk' for i in p['inputs']):raise RevivalError('V1 patch/sign pipeline supports monolithic APKs only. Split analysis and runtime installs are supported; a split patch adapter is not implemented.')
        work=self.store.directory(game_id)/'work'/uuid.uuid4().hex;work.mkdir(parents=True);decoded=work/'decoded'
        # Record a failed attempt without losing a previous working artifact.
        try:
            progress('Preparing the client')
            assets_only=all(o['file'].startswith('assets/') or o['type']=='patch_bytes' for o in plan['operations'])
            if assets_only:
                decoded.mkdir()
                with zipfile.ZipFile(self.store.base(p)) as z:
                    for op in plan['operations']:
                        target=decoded/op['file'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(op['file']))
            else:
                apktool('d','-f','-o',decoded,self.store.base(p))
            reviews=[]
            for op in plan['operations']:
                rel=safe_member(op['file']);f=decoded/pathlib.Path(*rel.parts)
                if not f.is_file() or f.is_symlink() or decoded.resolve() not in f.resolve().parents:raise RevivalError('Patch target missing or unsafe')
                raw=f.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=op['expected_sha256']:raise RevivalError('Patch precondition hash mismatch: '+op['file'])
                if op['type'] in getattr(adapter(p),'operation_types',()):
                    changed,review=adapter(p).apply_operation(op,raw)
                    f.write_bytes(changed);reviews.append(review)
                    continue
                if op['type']=='patch_bytes':
                    changed=bytearray(raw)
                    for patch in op['patches']:
                        offset=patch['offset'];old_bytes=bytes.fromhex(patch['old']);new_bytes=bytes.fromhex(patch['new'])
                        if offset<0 or changed[offset:offset+len(old_bytes)]!=old_bytes:raise RevivalError('Binary patch precondition mismatch: '+op['file'])
                        changed[offset:offset+len(old_bytes)]=new_bytes
                        reviews.append(f"{op['file']} @ {offset:#x}: {patch['old']} -> {patch['new']}; {patch.get('reason','')}\n")
                    f.write_bytes(changed);continue
                old=raw.decode('utf-8')
                if op['type']=='replace_text_file':new=op['content']
                elif op['type']=='replace_text':
                    expected=op.get('count',1)
                    if not op.get('old') or old.count(op['old'])!=expected:raise RevivalError('Exact replacement count mismatch')
                    new=old.replace(op['old'],op['new'])
                else:raise RevivalError('Unknown patch operation')
                reviews.append(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=op['file'],tofile=op['file'])))
                f.write_text(new,encoding='utf-8')
            (work/'changes.diff').write_text('\n'.join(reviews));atomic_json(work/'plan.json',plan)
            progress('Building the APK')
            if assets_only:
                changed={op['file'] for op in plan['operations']}
                with zipfile.ZipFile(self.store.base(p)) as original, zipfile.ZipFile(work/'unsigned.apk','w') as rebuilt:
                    for entry in original.infolist():
                        upper=entry.filename.upper()
                        if upper.startswith('META-INF/') and (upper.endswith(('.RSA','.DSA','.EC','.SF')) or upper=='META-INF/MANIFEST.MF'):continue
                        data=(decoded/entry.filename).read_bytes() if entry.filename in changed else original.read(entry.filename)
                        rebuilt.writestr(entry,data)
            else:
                apktool('b','-f',decoded,'-o',work/'unsigned.apk')
            # Do not override signing errors caused by invalid compiled manifests.
            from .analysis import manifest
            with zipfile.ZipFile(work/'unsigned.apk') as z:
                result=manifest(z.read('AndroidManifest.xml'))
                if result['package']!=plan.get('client_package',p['analysis']['metadata']['package']) or result['version_code']!=p['apk_version']['code']:raise RevivalError('Rebuilt package/version changed unexpectedly')
            command([tool('zipalign'),'-f','-p','4',work/'unsigned.apk',work/'aligned.apk'])
            progress('Signing and checking the APK')
            key,password=self._signing_identity()
            env=dict(os.environ);env['APKR_CURRENT_SIGN_PASS']=password
            command([tool('apksigner'),'sign','--ks',key,'--ks-pass','env:APKR_CURRENT_SIGN_PASS','--key-pass','env:APKR_CURRENT_SIGN_PASS','--out',work/'restored.apk',work/'aligned.apk'],env=env)
            verification=command([tool('apksigner'),'verify','--verbose','--print-certs',work/'restored.apk'])
            (work/'signature-verification.txt').write_text(verification)
            command([tool('zipalign'),'-c','-p','4',work/'restored.apk'])
            # Check original hash again after all tooling completes.
            self.store.load(game_id)
            restoration={'path':path,'operations':plan['operations'],'plan':plan,'artifact':str((work/'restored.apk').relative_to(self.store.directory(game_id))),'artifact_sha256':digest(work/'restored.apk'),'signature_verified':True,'client_package':result['package'],'diff':str((work/'changes.diff').relative_to(self.store.directory(game_id)))}
            if hasattr(adapter(p),'prepare_data'):
                progress('Setting up local services');restoration['backend_data']=adapter(p).prepare_data(self.store,p,work)
            # Publish the new artifact only after its service data is ready.
            # A failure/cancellation above must keep the old working reference.
            p['restoration']=restoration
            p['status']='Restoration In Progress';p['verification']=[];p['logs'].append({'message':'APK rebuilt, aligned, signed and signature verified. Gameplay remains unverified.'});self.store.save(p);return p
        except Exception as e:
            p['logs'].append({'message':'Preparation failed: '+str(e)});self.store.save(p);raise
    def _validate(self,p,plan,path):
        if plan.get('schema_version')!=1 or plan.get('apk_sha256')!=p['apk_sha256'] or plan.get('apk_version')!=p['apk_version'] or plan.get('path')!=path:raise RevivalError('Plan must match exact APK hash, version, schema and selected path')
        if plan.get('adapter')!=p.get('adapter') or path not in adapter(p).supported_paths:raise RevivalError('No implemented workflow for this adapter and path')
        if path=='rebuild' and plan.get('adapter')!='tapquest-v1':raise RevivalError('No implemented rebuild for this plan')
        if len(plan.get('operations',[]))>100:raise RevivalError('Too many operations')
        for op in plan.get('operations',[]):
            rel=safe_member(op.get('file',''));ext=rel.suffix.lower()
            plugin=adapter(p)
            if op.get('type') in getattr(plugin,'operation_types',()):
                plugin.validate_operation(op,p);continue
            if op.get('type')=='patch_bytes':
                # Binary patches are allowed only on files the game's reviewed plugin names.
                if op['file'] not in getattr(plugin,'binary_targets',()) or not re_hash(op.get('expected_sha256','')):raise RevivalError('Binary operation is restricted to files reviewed by the game plugin')
                if not op.get('patches') or len(op['patches'])>100:raise RevivalError('Invalid binary patch set')
                previous_end=-1
                for patch in sorted(op['patches'],key=lambda x:x.get('offset',-1)):
                    try:a=bytes.fromhex(patch['old']);b=bytes.fromhex(patch['new'])
                    except (ValueError,KeyError):raise RevivalError('Invalid binary patch bytes')
                    offset=patch.get('offset');
                    if type(offset) is not int or offset<0 or offset<previous_end or not a or len(a)!=len(b) or len(a)>128:raise RevivalError('Binary patches must be non-overlapping, bounded and same length')
                    previous_end=offset+len(a)
                continue
            if ext not in {'.json','.xml','.smali','.txt','.cfg','.ini','.properties','.plist'}:raise RevivalError('Only explicit text file operations are supported in V1')
            if op.get('type') not in {'replace_text_file','replace_text'} or not re_hash(op.get('expected_sha256','')):raise RevivalError('Invalid operation or missing precondition hash')
            if len(op.get('content',''))>2*1024**2:raise RevivalError('Patch content exceeds limit')
    def _signing_identity(self):
        key=os.getenv('APKR_KEYSTORE');password=os.getenv('APKR_SIGNING_PASSWORD')
        if key:
            if not password:raise RevivalError('Set APKR_SIGNING_PASSWORD for your keystore')
            return key,password
        d=self.store.root/'signing';d.mkdir(exist_ok=True,mode=0o700);key=d/'local.p12';secret=d/'password.txt'
        if key.exists():
            if not secret.exists():raise RevivalError('Signing password missing. Restore private password.txt or select your own key.')
            return key,secret.read_text().strip()
        password=secrets.token_urlsafe(32)
        secret.write_text(password);secret.chmod(0o600)
        env=dict(os.environ);env['APKR_CURRENT_SIGN_PASS']=password
        command([tool('keytool'),'-genkeypair','-keystore',key,'-storetype','PKCS12','-alias','revival','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=APK Revival local user','-storepass:env','APKR_CURRENT_SIGN_PASS','-keypass:env','APKR_CURRENT_SIGN_PASS'],env=env)
        key.chmod(0o600);return key,password

def re_hash(s):return len(s)==64 and all(c in '0123456789abcdef' for c in s)

