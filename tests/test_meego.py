"""Opt-in real APK tests. Android gameplay is not mocked into a passing claim."""
import copy,json,os,pathlib,socket,tempfile,unittest,urllib.parse,urllib.request,zipfile
from apk_revival.store import Store
from apk_revival.launcher.service import Launcher
from apk_revival.meego.adapter import ORIGINAL_SHA,PACKAGE
from apk_revival.meego.backend import MeegoBackend,config_path
from apk_revival.meego.verification import GuidedTest
from apk_revival.saves import Saves
from apk_revival.restoration import Restorer
from apk_revival.util import RevivalError,atomic_json,digest,command,tool

@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'),'Supply the exact privately owned Meego APK and real signing tools')
class RealMeegoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.store=Store(self.root/'private');self.launcher=Launcher(self.store);self.backend=None
        self.p=self.launcher.jobs.run('import',lambda c:self.launcher.import_game(pathlib.Path(os.environ['APKR_MEEGO_APK']),[],c));self.game=self.p['id'];self.p=self.launcher.jobs.run('prepare',lambda c:self.launcher.prepare(self.game,'local_backend',c))
    def tearDown(self):
        if self.backend:self.backend.stop()
        self.launcher.shutdown();self.temp.cleanup()
    def start(self,port=0):self.backend=MeegoBackend(self.store.directory(self.game),config_path(self.store,self.p),port).start();return self.backend
    def request(self,path,body=None):
        data=None if body is None else urllib.parse.urlencode(body).encode()
        with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{self.backend.port}/'+path,data=data),timeout=10) as r:return json.load(r)
    def test_real_signed_client_and_protocol_save_export(self):
        self.assertEqual(self.p['apk_sha256'],ORIGINAL_SHA);self.assertEqual(self.p['restoration']['client_package'],PACKAGE);self.assertTrue(self.p['restoration']['signature_verified']);artifact=self.store.directory(self.game)/self.p['restoration']['artifact'];self.assertIn('Verifies',command([tool('apksigner'),'verify','--verbose',artifact]))
        self.start();self.assertEqual(self.request('health')['token'],self.backend.token);self.assertEqual(len(self.request('game/login/oauth')['game_state']['all_villagers']),2)
        before=copy.deepcopy(self.backend.server.state.data);self.request('game/village/place_building',{'building_type_id':5,'location':676,'orientation':1});after=copy.deepcopy(self.backend.server.state.data);self.assertGreater(len(after['game_state']['buildings']),len(before['game_state']['buildings']));self.assertIn('exception',self.request('game/village/unknown'));saved=copy.deepcopy(self.backend.server.state.data);self.backend.stop();self.start();self.assertEqual(self.backend.server.state.data,saved);self.backend.stop()
        backup=Saves(self.store).backup(self.game);changed=copy.deepcopy(saved);changed['game_user']['username']='temporary';atomic_json(self.store.directory(self.game)/'saves/village.json',changed);self.assertTrue(Saves(self.store).restore(self.game,backup)['previous_backup'])
        out=self.root/'export.zip';self.launcher.jobs.run('export',lambda c:self.launcher.export(self.game,out,c))
        with zipfile.ZipFile(out) as z:
            self.assertIn('backend-data/local-rules.json',z.namelist());self.assertIn('restored.apk',z.namelist());self.assertFalse(any('/saves/' in x or '/signing/' in x or '/originals/' in x for x in z.namelist()))
        self.assertNotEqual(self.store.load(self.game)['status'],'Verified Offline');self.assertEqual(digest(pathlib.Path(os.environ['APKR_MEEGO_APK'])),ORIGINAL_SHA)
    def test_binary_precondition_failure_preserves_previous_artifact(self):
        old=self.p['restoration']['artifact_sha256'];plan=Restorer(self.store).plan(self.game,'local_backend');plan['operations'][0]['patches'][0]['old']='00000000';file=self.root/'bad-plan.json';atomic_json(file,plan)
        with self.assertRaisesRegex(RevivalError,'Binary patch precondition'):Restorer(self.store).prepare(self.game,'local_backend',file)
        self.assertEqual(self.store.load(self.game)['restoration']['artifact_sha256'],old)
        for path in ['offline_patch','rebuild']:
            with self.assertRaisesRegex(RevivalError,'local backend path only'):Restorer(self.store).plan(self.game,path)
    def test_startup_failure_recovery_and_nonce(self):
        with socket.socket() as busy:
            busy.bind(('127.0.0.1',0));busy.listen();port=busy.getsockname()[1]
            with self.assertRaisesRegex(RevivalError,'startup failed'):MeegoBackend(self.store.directory(self.game),config_path(self.store,self.p),port).start()
        self.start(port);old=self.backend.token;self.backend.stop();self.start(port);self.assertNotEqual(old,self.request('health')['token'])
    def test_guided_test_requires_observations_and_never_certifies_without_android(self):
        test=GuidedTest(self.store,self.game)
        with self.assertRaisesRegex(RevivalError,'in order'):test.confirm_action()
        record=test.finish(False,'No Android runtime available in build environment');self.assertFalse(record['passed']);self.assertFalse(record['external_network_blocked']);self.assertNotEqual(self.store.load(self.game)['status'],'Verified Offline')
    def test_cleanup_restores_guard_even_if_game_stop_fails(self):
        from types import SimpleNamespace
        test=GuidedTest(self.store,self.game);cleaned=[]
        def fail():raise RevivalError('Synthetic disconnect during stop')
        test.r=SimpleNamespace(adb=lambda *a,**k:'command-boundary test double',stop=fail)
        test.guard=SimpleNamespace(__exit__=lambda *args:cleaned.append(True))
        record=test.finish(False,'Cancelled command-boundary test');self.assertEqual(cleaned,[True]);self.assertFalse(record['passed']);self.assertIn('cleanup_error',record)

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    HAS_QT=True
except ImportError:HAS_QT=False

@unittest.skipUnless(HAS_QT and os.getenv('APKR_MEEGO_APK') and os.getenv('APKR_V2_UI_TEST'),'Enable Qt and the privately owned Meego APK')
class MeegoGUI(unittest.TestCase):
    def test_import_prepare_report_and_guided_cancel_actual_widgets(self):
        from apk_revival.launcher.ui import Window
        from apk_revival.launcher.style import STYLE
        app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
        with tempfile.TemporaryDirectory() as temp:
            w=Window(Store(pathlib.Path(temp)/'private'));w.service.runtime_manager.discover=lambda *a,**k:{'ready':False,'devices':[],'waydroid':False,'steam_os':False};w.show()
            def wait():
                import time
                deadline=time.monotonic()+30
                while w.worker and time.monotonic()<deadline:app.processEvents();QTest.qWait(20)
                self.assertIsNone(w.worker);app.processEvents()
            QTest.qWait(100);wait()
            def fill():
                d=app.activeModalWidget();d.apk.setText(os.environ['APKR_MEEGO_APK']);d.add.click()
            QTimer.singleShot(50,fill);w.add_button.click();wait();self.assertEqual(w.profile()['adapter'],'meego-1.32');w.prepare_button.click();wait();self.assertTrue(w.profile()['restoration']['signature_verified']);self.assertEqual(w.play_button.text(),'Set up Android')
            QTimer.singleShot(100,lambda:app.activeModalWidget().reject());w.test_offline();self.assertFalse(w.profile()['verification'][-1]['passed']);self.assertNotEqual(w.profile()['status'],'Verified Offline');w.close();app.processEvents()
