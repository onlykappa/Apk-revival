"""Opt-in real SDK/apktool build integration; never mocks Android gameplay."""
import os,pathlib,tempfile,unittest,zipfile,json
from apk_revival.store import Store
from apk_revival.analysis import analyze,manifest
from apk_revival.restoration import Restorer
from apk_revival.exporter import export_game
from apk_revival.util import digest,command,tool

@unittest.skipUnless(os.getenv('APKR_TEST_APK'),'Set APKR_TEST_APK to a built Tap Quest APK for actual-tool integration')
class RealAPKTests(unittest.TestCase):
    def test_both_signed_paths_export_without_private_data(self):
        original=pathlib.Path(os.environ['APKR_TEST_APK']);original_hash=digest(original)
        with tempfile.TemporaryDirectory() as t:
            root=pathlib.Path(t);s=Store(root/'private');p=s.import_game(original);game=p['id'];p=analyze(s,game)
            self.assertEqual(p['analysis']['metadata']['package'],'org.apkrevival.tapquest');self.assertEqual(p['apk_version']['code'],'1')
            for path in ['offline_patch','local_backend']:
                plan=Restorer(s).plan(game,path);p=Restorer(s).prepare(game,path)
                artifact=s.directory(game)/p['restoration']['artifact'];self.assertIn('Verifies',command([tool('apksigner'),'verify','--verbose',artifact]))
                with zipfile.ZipFile(artifact) as z:
                    c=json.loads(z.read('assets/revival.json'));self.assertEqual(c['mode'],'offline' if path=='offline_patch' else 'remote');self.assertTrue(z.read('classes.dex').startswith(b'dex\n'))
                self.assertTrue(p['restoration']['signature_verified']);self.assertNotEqual(digest(artifact),original_hash)
                out=root/(path+'.zip');export_game(s,game,out)
                with zipfile.ZipFile(out) as z:
                    self.assertIn('restored.apk',z.namelist());self.assertFalse(any('password' in n or '.p12' in n or '/saves/' in n or '/originals/' in n for n in z.namelist()));self.assertEqual(json.loads(z.read('profile.json'))['status'],'Exported but Unverified')
                self.assertEqual(digest(original),original_hash)
