import hashlib, json, os, pathlib, struct, tempfile, unittest, zipfile
from unittest.mock import patch
from apk_revival.analysis import analyze, dex_strings, manifest
from apk_revival.store import Store
from apk_revival.util import RevivalError, digest, inspect_zip
from apk_revival.restoration import Restorer
from apk_revival.exporter import export_game
from apk_revival.saves import Saves
from apk_revival.backend import Progress
from apk_revival.verification import CHECKS, passes
from apk_revival.runtime import WaydroidRuntime


def make_apk(path,fixture=True,package=None,version='1',split=False,extra=None):
    package=package or ('org.apkrevival.tapquest' if fixture else 'org.example.unknown')
    manifest_xml=f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{package}" android:versionCode="{version}" android:versionName="1.0"'+(' split="config.arm"' if split else '')+'><uses-sdk android:minSdkVersion="23" android:targetSdkVersion="28"/><uses-permission android:name="android.permission.INTERNET"/><application><activity android:name=".Main"/></application></manifest>'
    # Structural test-only DEX header with real string table layout; not runnable Android bytecode.
    strings=['https://retired.example.invalid/state','Landroid/content/SharedPreferences;','assetbundle download']
    data=bytearray(112+4*len(strings));data[:8]=b'dex\n035\0';struct.pack_into('<II',data,56,len(strings),112)
    for n,s in enumerate(strings):
        struct.pack_into('<I',data,112+n*4,len(data));data.extend(bytes([len(s)])+s.encode()+b'\0')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('AndroidManifest.xml',manifest_xml);z.writestr('classes.dex',data)
        if fixture:z.writestr('assets/revival.json','{"fixture":"tapquest-v1","mode":"remote","endpoint":"https://retired.tapquest.invalid"}\n')
        for k,v in (extra or {}).items():z.writestr(k,v)
    return path

class Pipeline(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.store=Store(self.root/'private');self.apk=make_apk(self.root/'test.apk');self.p=self.store.import_game(self.apk);self.game=self.p['id']
    def tearDown(self):self.temp.cleanup()
    def test_original_copy_hash_and_idempotence(self):
        self.assertEqual(digest(self.store.base(self.p)),digest(self.apk));self.assertEqual(self.store.import_game(self.apk)['id'],self.game)
        self.assertTrue((self.store.directory(self.game)/'history/000001.json').exists())
    def test_original_mutation_rejected(self):
        self.store.base(self.p).chmod(0o600);self.store.base(self.p).write_bytes(b'tamper')
        with self.assertRaisesRegex(RevivalError,'hash changed'):self.store.load(self.game)
    def test_version_separation(self):
        other=make_apk(self.root/'v2.apk',version='2');self.assertNotEqual(self.store.import_game(other)['id'],self.game)
    def test_unsupported_format(self):
        unknown=self.root/'bad.xapk';unknown.write_bytes(b'bad')
        with self.assertRaises(RevivalError):self.store.import_game(unknown)
    def test_invalid_executable(self):
        empty=self.root/'empty.apk'
        with zipfile.ZipFile(empty,'w') as z:z.writestr('AndroidManifest.xml','<manifest/>')
        with self.assertRaisesRegex(RevivalError,'executable'):self.store.import_game(empty)
    def test_traversal_and_duplicate_rejected(self):
        bad=self.root/'bad.apk'
        with zipfile.ZipFile(bad,'w') as z:z.writestr('../escape','bad')
        with self.assertRaises(RevivalError):inspect_zip(bad)
        with zipfile.ZipFile(bad,'w') as z:
            z.writestr('same','one');z.writestr('same','two')
        with self.assertRaises(RevivalError):inspect_zip(bad)
    def test_archive_symlink_rejected(self):
        bad=self.root/'link.apk'
        with zipfile.ZipFile(bad,'w') as z:
            i=zipfile.ZipInfo('link');i.external_attr=0o120777<<16;z.writestr(i,'/tmp/x')
        with self.assertRaises(RevivalError):inspect_zip(bad)
    def test_attach_roles_and_assets(self):
        obb=self.root/'main.1.org.apkrevival.tapquest.obb';obb.write_bytes(b'asset');log=self.root/'launch.log';log.write_text('private')
        p=self.store.attach(self.game,[obb,log]);self.assertEqual([i['role'] for i in p['inputs']],['base_apk','obb','log'])
    def test_static_evidence_not_runtime_claim(self):
        p=analyze(self.store,self.game);a=p['analysis'];self.assertEqual(a['metadata']['package'],'org.apkrevival.tapquest');self.assertEqual(p['status'],'Analyzed');self.assertEqual(p['verification'],[])
        self.assertTrue(a['endpoints']);self.assertTrue(any('unproven' in x['classification'] for x in a['endpoints']))
    def test_unknown_adapter_needs_evidence(self):
        apk=make_apk(self.root/'unknown.apk',fixture=False);p=self.store.import_game(apk);p=analyze(self.store,p['id']);self.assertEqual(p['status'],'Needs Evidence')
        with self.assertRaisesRegex(RevivalError,'no trusted game adapter'):Restorer(self.store).prepare(p['id'],'offline_patch')
    def test_arm_architecture_evidence(self):
        apk=make_apk(self.root/'arm.apk',fixture=False,extra={'lib/arm64-v8a/libunity.so':b'fake'});p=self.store.import_game(apk);p=analyze(self.store,p['id']);self.assertEqual(p['analysis']['engine'],'Unity');self.assertEqual(p['analysis']['abis'],['arm64-v8a'])
    def test_split_version_mismatch(self):
        split=make_apk(self.root/'split.apk',version='2',split=True);self.store.attach(self.game,[split]);p=analyze(self.store,self.game);self.assertTrue(p['analysis']['input_errors'])
        with self.assertRaises(RevivalError):Restorer(self.store).plan(self.game,'offline_patch')
    def test_plan_bound_to_exact_hash_and_version(self):
        analyze(self.store,self.game);r=Restorer(self.store);plan=r.plan(self.game,'offline_patch');p=self.store.load(self.game)
        plan['apk_sha256']='0'*64
        with self.assertRaisesRegex(RevivalError,'exact APK'):r._validate(p,plan,'offline_patch')
    def test_plan_traversal_rejected(self):
        analyze(self.store,self.game);r=Restorer(self.store);plan=r.plan(self.game,'offline_patch');plan['operations'][0]['file']='../oops.json'
        with self.assertRaises(RevivalError):r._validate(self.store.load(self.game),plan,'offline_patch')
    def test_rebuild_separate_and_private_export(self):
        analyze(self.store,self.game);p=Restorer(self.store).prepare(self.game,'rebuild');d=self.store.directory(self.game);(d/'saves').mkdir();(d/'saves/rebuild.json').write_text('{"coins":4,"level":1}')
        out=self.root/'rebuild.zip';result=export_game(self.store,self.game,out)
        with zipfile.ZipFile(out) as z:
            names=z.namelist();self.assertNotIn('restored.apk',names);self.assertFalse(any('saves/' in n or 'signing/' in n or 'originals/' in n for n in names));profile=json.loads(z.read('profile.json'));self.assertEqual(profile['verification'],[]);self.assertEqual(profile['status'],'Exported but Unverified')
            hashes=json.loads(z.read('hashes.json'))
            for f,h in hashes.items():self.assertEqual(hashlib.sha256(z.read(f)).hexdigest(),h)
    def test_save_backup_restore_reversible(self):
        analyze(self.store,self.game);Restorer(self.store).prepare(self.game,'rebuild');d=self.store.directory(self.game);progress=Progress(d/'saves/rebuild.json');progress.collect();backup=Saves(self.store).backup(self.game);progress.collect();result=Saves(self.store).restore(self.game,backup)
        self.assertTrue(result['previous_backup']);self.assertEqual(Progress(d/'saves/rebuild.json').get()['coins'],1)
    def test_cross_version_backup_rejected(self):
        analyze(self.store,self.game);Restorer(self.store).prepare(self.game,'rebuild');Progress(self.store.directory(self.game)/'saves/rebuild.json').collect();backup=Saves(self.store).backup(self.game)
        other=self.store.import_game(make_apk(self.root/'other.apk',version='2'));analyze(self.store,other['id']);Restorer(self.store).prepare(other['id'],'rebuild')
        with self.assertRaisesRegex(RevivalError,'different APK'):Saves(self.store).restore(other['id'],backup)
    def test_gate_requires_every_gameplay_check(self):
        r={'kind':'android_gameplay','external_network_blocked':True,'checks':{k:True for k in CHECKS}};self.assertTrue(passes(r))
        for k in CHECKS:
            r['checks'][k]=False;self.assertFalse(passes(r));r['checks'][k]=True
        r['external_network_blocked']=False;self.assertFalse(passes(r));r['kind']='host_protocol';self.assertFalse(passes(r))
    def test_shell_arguments_quoted(self):
        r=WaydroidRuntime('chosen-device')
        with patch('apk_revival.runtime.command',return_value=''),patch('apk_revival.runtime.tool',return_value='adb') as _:
            r.shell('echo','$(touch /tmp/NEVER)')
            from apk_revival.runtime import command
            args=command.call_args.args[0];self.assertEqual(args[:3],['adb','-s','chosen-device']);self.assertIn("'$(touch /tmp/NEVER)'",args[-1])
    def test_missing_runtime_cannot_verify(self):
        from apk_revival.verification import verify
        analyze(self.store,self.game)
        with patch('apk_revival.runtime.WaydroidRuntime.probe',return_value={'available':False}):record=verify(self.store,self.game)
        self.assertFalse(record['passed']);self.assertNotEqual(self.store.load(self.game)['status'],'Verified Offline')

if __name__=='__main__':unittest.main()

class InputRoleTests(unittest.TestCase):
    def test_private_json_and_dat_not_exported_as_assets(self):
        with tempfile.TemporaryDirectory() as t:
            root=pathlib.Path(t);apk=make_apk(root/'game.apk');private=root/'private.json';private.write_text('{"secret":"must remain local"}');binary=root/'save.dat';binary.write_bytes(b'private')
            s=Store(root/'data');p=s.import_game(apk,[private,binary]);game=p['id'];self.assertEqual([i['role'] for i in p['inputs'][1:]],['evidence','save']);analyze(s,game);Restorer(s).prepare(game,'rebuild');export_game(s,game,root/'bundle.zip')
            with zipfile.ZipFile(root/'bundle.zip') as z:self.assertFalse(any(n.startswith('support/') for n in z.namelist()))
    def test_explicit_asset_role_and_runtime_log_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root=pathlib.Path(t);asset=root/'assets.dat';asset.write_bytes(b'asset');log=root/'launch.log';log.write_text('FATAL EXCEPTION: main\njava.net.UnknownHostException: retired.invalid\n')
            s=Store(root/'data');p=s.import_game(make_apk(root/'game.apk'),[('asset',asset),('log',log)]);p=analyze(s,p['id']);self.assertEqual(p['inputs'][1]['role'],'asset');self.assertEqual(len(p['analysis']['supplied_log_observations']),2)
