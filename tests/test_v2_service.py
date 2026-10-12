import json,os,pathlib,tempfile,threading,unittest,zipfile
from unittest.mock import patch
from apk_revival.store import Store
from apk_revival.launcher.jobs import Jobs,Cancelled
from apk_revival.launcher.presentation import readiness
from apk_revival.launcher.runtime_setup import RuntimeManager,ManagedAndroid
from apk_revival.launcher.service import Launcher
from apk_revival.launcher.install import install
from apk_revival.util import RevivalError,digest
from test_pipeline import make_apk

class V2ServiceTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.store=Store(self.root/'private');self.s=Launcher(self.store)
    def tearDown(self):self.s.shutdown();self.temp.cleanup()
    def job(self,label,fn):return self.s.jobs.run(label,fn)
    def import_fixture(self):return self.job('import',lambda ctx:self.s.import_game(make_apk(self.root/'game.apk'),[],ctx))
    def test_unknown_game_never_ready(self):
        p=self.job('import',lambda ctx:self.s.import_game(make_apk(self.root/'unknown.apk',fixture=False),[],ctx));r=readiness(p,True);self.assertFalse(r['play']);self.assertFalse(r['prepare']);self.assertEqual(r['label'],'Restoration work needed')
        with self.assertRaisesRegex(RevivalError,'game-specific'):self.job('prepare',lambda ctx:self.s.prepare(p['id'],None,ctx))
    def test_rebuild_lifecycle_backup_export_and_private_diagnostics(self):
        p=self.import_fixture();game=p['id'];p=self.job('prepare',lambda ctx:self.s.prepare(game,'rebuild',ctx));self.assertEqual(readiness(p)['label'],'Separate rebuild ready')
        self.job('play',lambda ctx:self.s.play(game,ctx));self.assertEqual(self.s.active['kind'],'rebuild');self.s.stop()
        from apk_revival.backend import Progress
        Progress(self.store.directory(game)/'saves/rebuild.json').collect();backup=self.job('backup',lambda ctx:self.s.backup(game,ctx));Progress(self.store.directory(game)/'saves/rebuild.json').collect();self.job('restore',lambda ctx:self.s.restore(game,backup,ctx));self.assertEqual(Progress(self.store.directory(game)/'saves/rebuild.json').get()['coins'],1)
        out=self.root/'bundle.zip';self.job('export',lambda ctx:self.s.export(game,out,ctx))
        with zipfile.ZipFile(out) as z:self.assertFalse(any('/saves/' in x for x in z.namelist()))
        diag=self.root/'diag.zip';self.job('diagnostics',lambda ctx:self.s.diagnostics(game,diag,ctx))
        with zipfile.ZipFile(diag) as z:
            self.assertEqual(set(z.namelist()),{'diagnostics.json','README.txt'});self.assertNotIn(str(self.store.root),z.read('diagnostics.json').decode())
        self.assertNotEqual(self.store.load(game)['status'],'Verified Offline')
    def test_actual_job_steps_and_failure(self):
        jobs=Jobs();snapshots=[]
        def work(ctx):ctx.step('One');ctx.step('Two');raise RevivalError('Actionable failure')
        with self.assertRaises(RevivalError):jobs.run('test',work,snapshots.append)
        self.assertEqual(jobs.history[-1].state,'failed');self.assertEqual(jobs.history[-1].steps[0]['state'],'done');self.assertEqual(jobs.history[-1].steps[1]['state'],'failed');self.assertEqual(snapshots[1]['steps'][0]['state'],'running')
    def test_cancellation_and_exclusive_jobs(self):
        jobs=Jobs()
        def work(ctx):
            ctx.step('first');jobs.cancel();ctx.step('never')
        with self.assertRaises(Cancelled):jobs.run('cancel',work)
        self.assertEqual(jobs.history[-1].state,'cancelled')
        jobs.lock.acquire()
        try:
            with self.assertRaisesRegex(RevivalError,'Another task'):jobs.run('blocked',lambda ctx:None)
        finally:jobs.lock.release()
    def test_discovery_connects_known_waydroid_ip(self):
        def run(args,**kwargs):
            if args[-1]=='status':return 'Session:\tRUNNING\nContainer:\tRUNNING\nIP address:\t192.168.240.112\n'
            if 'devices' in args:return 'List of devices attached\n192.168.240.112:5555 device model:Waydroid\n'
            return 'connected'
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:n),patch('apk_revival.launcher.runtime_setup.command',side_effect=run) as cmd:
            r=RuntimeManager().discover();self.assertTrue(r['ready']);self.assertEqual(r['devices'][0]['serial'],'192.168.240.112:5555');self.assertTrue(any(c.args[0]==['adb','connect','192.168.240.112:5555'] for c in cmd.call_args_list))
    def test_multiple_devices_require_selection(self):
        manager=RuntimeManager();manager.discover=lambda:{'ready':True,'waydroid':False,'devices':[{'serial':'one','state':'device'},{'serial':'two','state':'device'}]}
        with self.assertRaisesRegex(RevivalError,'More than one'):manager.ensure()
        self.assertEqual(manager.ensure('two'),'two')
    def test_manual_connection_rejects_shell_payload(self):
        with self.assertRaises(RevivalError):RuntimeManager().connect_manual('1.2.3.4; touch /tmp/never')
    def test_user_local_install_keeps_prior_install(self):
        source=self.root/'app';source.mkdir();(source/'APK-Revival').write_text('fake test binary');(source/'_internal/resources').mkdir(parents=True);(source/'_internal/resources/apk-revival.svg').write_text('<svg/>');home=self.root/'home';home.mkdir();(home/'Desktop').mkdir()
        first=install(source,home);(source/'APK-Revival').write_text('updated');second=install(source,home);self.assertTrue(pathlib.Path(second['previous_install']).exists());self.assertIn('APK Revival',pathlib.Path(second['desktop_file']).read_text());self.assertTrue((home/'Desktop/APK Revival.desktop').exists())
    def test_prepare_requires_tools_and_does_not_claim_verification(self):
        p=self.import_fixture()
        with patch('apk_revival.launcher.service.health',return_value={'preparation_ready':False}):
            with self.assertRaisesRegex(RevivalError,'Preparation tools'):self.job('prepare',lambda ctx:self.s.prepare(p['id'],'offline_patch',ctx))
        self.assertNotEqual(self.store.load(p['id'])['status'],'Verified Offline')
    def test_cached_install_requires_actual_guest_hash(self):
        p=self.import_fixture();from apk_revival.restoration import Restorer
        # Test only Android command boundary. Artifact itself is a structural test APK.
        artifact=self.store.directory(p['id'])/'restored.apk';artifact.write_bytes(self.store.base(p).read_bytes());p['restoration'].update(artifact='restored.apk',artifact_sha256=digest(artifact))
        r=ManagedAndroid('test-guest');r.compatible=lambda _:{};r.shell=lambda *a,**kw:'package:/data/app/demo/base.apk\n' if a[:2]==('pm','path') else digest(artifact)+' base.apk\n'
        with patch('apk_revival.runtime.WaydroidRuntime.install') as base:r.install(self.store,p);base.assert_not_called();self.assertFalse(r.installed_now)
        r.shell=lambda *a,**kw:'package:/data/app/demo/base.apk\n' if a[:2]==('pm','path') else '0'*64+' base.apk\n'
        with patch('apk_revival.runtime.WaydroidRuntime.install') as base:r.install(self.store,p);base.assert_called_once();self.assertTrue(r.installed_now)

if __name__=='__main__':unittest.main()

class NativeExportTests(unittest.TestCase):
    def test_native_export_excludes_fixture_apk_and_private_saves(self):
        import sys
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);app=root/'application';(app/'_internal/resources').mkdir(parents=True);(app/'APK-Revival').write_bytes(b'fake executable for filesystem boundary test');(app/'_internal/resources/tapquest-original.apk').write_bytes(b'fixture');(app/'_internal/library.so').write_bytes(b'fake framework')
            s=Launcher(Store(root/'private'));p=s.jobs.run('import',lambda c:s.import_game(make_apk(root/'game.apk'),[],c));s.jobs.run('prepare',lambda c:s.prepare(p['id'],'rebuild',c));out=root/'native.zip'
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(app/'APK-Revival')):result=s.jobs.run('export',lambda c:s.export(p['id'],out,c))
            self.assertTrue(result['native_launcher'])
            with zipfile.ZipFile(out) as z:
                self.assertIn('Play-Game',z.namelist());self.assertNotIn('_internal/resources/tapquest-original.apk',z.namelist());self.assertFalse(any('/saves/' in x for x in z.namelist()));self.assertIn('START-HERE.txt',z.namelist())
                import hashlib
                for name,sha in json.loads(z.read('hashes.json')).items():self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),sha)
