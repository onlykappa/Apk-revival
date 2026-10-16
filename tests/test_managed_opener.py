import pathlib,tempfile,unittest,zipfile,json
from unittest.mock import patch,Mock
from apk_revival.launcher.apk_info import inspect_apk,manifest_info
from apk_revival.launcher.runtime_setup import RuntimeManager,ManagedAndroid
from apk_revival.launcher.service import Launcher
from apk_revival.launcher.presentation import readiness
from apk_revival.launcher.tools_setup import configure
from apk_revival.store import Store
from apk_revival.runtime import WaydroidRuntime
from apk_revival.util import RevivalError,digest
from test_pipeline import make_apk

class OpenerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);configure()
    def tearDown(self):self.temp.cleanup()
    def profile(self):
        launcher=Launcher(Store(self.root/'store'))
        p=launcher.jobs.run('Import',lambda ctx:launcher.import_game(make_apk(self.root/'game.apk',fixture=False),[],ctx))
        return launcher,p
    def test_import_without_adapter_enables_play(self):
        launcher,p=self.profile();self.assertTrue(readiness(p)['play']);self.assertIsNone(p['adapter']);self.assertTrue(p['launcher']['apk']['package']);launcher.shutdown()
    def test_manifest_selects_launcher_alias_not_first_activity(self):
        apk=self.root/'alias.apk'
        with zipfile.ZipFile(apk,'w') as z:z.writestr('AndroidManifest.xml','''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="game.example"><application><activity android:name=".Settings"/><activity-alias android:name=".Play" android:targetActivity=".Game"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity-alias></application></manifest>''')
        self.assertEqual(manifest_info(apk)['launch_activity'],'game.example.Play')
    def test_original_play_preserves_restoration_state_and_uses_no_backend(self):
        launcher,p=self.profile();runtime=Mock();launcher.runtime_factory=lambda serial:runtime
        launcher.runtime_manager.ensure=Mock(return_value='fresh-ip:5555')
        result=launcher.jobs.run('Play',lambda ctx:launcher.play(p['id'],ctx))
        self.assertEqual(result['kind'],'android');runtime.install.assert_called_once();self.assertTrue(runtime.install.call_args.kwargs['original']);runtime.start_backend.assert_not_called();runtime.launch.assert_called_once();self.assertIsNone(launcher.store.load(p['id'])['restoration']['artifact']);launcher.shutdown()
    def test_prepared_play_keeps_signed_artifact_and_backend(self):
        launcher,p=self.profile();artifact=launcher.store.directory(p['id'])/'restored.apk';artifact.write_bytes(launcher.store.base(p).read_bytes());p['restoration'].update(path='local_backend',artifact='restored.apk',artifact_sha256=digest(artifact),client_package='game.restored');launcher.store.save(p)
        runtime=Mock();launcher.runtime_factory=lambda serial:runtime;launcher.runtime_manager.ensure=Mock(return_value='new-ip:5555')
        launcher.jobs.run('Play',lambda ctx:launcher.play(p['id'],ctx));runtime.start_backend.assert_called_once();self.assertNotIn('original',runtime.install.call_args.kwargs);self.assertEqual(digest(artifact),p['restoration']['artifact_sha256']);launcher.shutdown()
    def test_changed_artifact_does_not_fall_back_to_original(self):
        launcher,p=self.profile();p['restoration'].update(path='offline_patch',artifact='missing.apk',artifact_sha256='0'*64);launcher.store.save(p)
        with self.assertRaisesRegex(RevivalError,'missing or changed'):launcher.jobs.run('Play',lambda ctx:launcher.play(p['id'],ctx))
        launcher.shutdown()
    def test_boot_uses_discovered_ip_over_old_preference(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'ready':True,'waydroid':True,'ip':'192.168.240.99','devices':[{'state':'device','serial':'192.168.240.99:5555'},{'state':'device','serial':'old'}]}
        with patch.object(WaydroidRuntime,'shell',side_effect=['1','Display 0','package:/system/framework/framework-res.apk']):self.assertEqual(manager.ensure('old'),'192.168.240.99:5555')
    def test_unrelated_device_never_auto_selected(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'ready':False,'waydroid':False,'devices':[{'state':'device','serial':'phone'}]}
        with self.assertRaisesRegex(RevivalError,'not connected'):manager.ensure()
    def test_launcher_resolves_main_category_and_rejects_android_error(self):
        runtime=WaydroidRuntime('test');p={'restoration':{},'analysis':{'metadata':{'package':'game.example'}}}
        runtime.shell=Mock(side_effect=['game.example/.Alias','Error: Activity class does not exist'])
        with patch('apk_revival.runtime.command'):
            with self.assertRaisesRegex(RevivalError,'rejected'):runtime.launch(p)
        self.assertIn('android.intent.category.LAUNCHER',runtime.shell.call_args_list[0].args)
    def test_arm_legacy_compatible_when_translation_advertised(self):
        runtime=WaydroidRuntime('test');runtime.probe=lambda:{'available':True,'abis':['x86_64','armeabi-v7a'],'sdk':'30'}
        runtime.compatible({'analysis':{'abis':['armeabi'],'metadata':{'min_sdk':'9'},'input_errors':[]}})
    def test_arm_mismatch_reports_actual_runtime_abis(self):
        runtime=WaydroidRuntime('test');runtime.probe=lambda:{'available':True,'abis':['x86_64'],'sdk':'30'}
        with self.assertRaisesRegex(RevivalError,'Architecture mismatch'):runtime.compatible({'analysis':{'abis':['arm64-v8a'],'metadata':{'min_sdk':'9'},'input_errors':[]}})
    def test_existing_apk_hash_skips_install(self):
        launcher,p=self.profile();runtime=ManagedAndroid('test');runtime.compatible=lambda p:{}
        runtime.shell=Mock(side_effect=['package:/data/app/game/base.apk',p['apk_sha256']+' base.apk'])
        with patch.object(WaydroidRuntime,'install') as install:runtime.install(launcher.store,p,original=True);install.assert_not_called()
        launcher.shutdown()
    def test_graphical_bundle_supervisor_never_spawns_terminal(self):
        manager=RuntimeManager()
        with patch('apk_revival.launcher.runtime_setup.subprocess.Popen') as start:manager.start_steam_bundle()
        self.assertEqual(start.call_args.args[0][0],'/bin/bash');self.assertIn('managed-waydroid.sh',start.call_args.args[0][1]);self.assertIn('SUDO_ASKPASS',start.call_args.kwargs['env']);manager.bundle_log.close()
    def test_real_meego_package_metadata(self):
        path=pathlib.Path('/home/deck/Applications/MeegoOffline/Meego-Offline.apk')
        if not path.is_file():self.skipTest('Private Meego APK is unavailable')
        info=inspect_apk(path,self.root);self.assertEqual(info['package'],'ata.fresh.meego');self.assertEqual(info['launch_activity'],'com.apportable.activity.VerdeActivity');self.assertIn('armeabi',info['abis']);self.assertTrue(pathlib.Path(info['icon']).is_file())

class SteamShortcutTests(unittest.TestCase):
    def test_registration_preserves_other_shortcuts_and_is_idempotent(self):
        from apk_revival.launcher.steam import encode,parse,register
        with tempfile.TemporaryDirectory() as temp:
            home=pathlib.Path(temp);config=home/'.local/share/Steam/userdata/123/config';config.mkdir(parents=True)
            path=config/'shortcuts.vdf';original=[(0,b'shortcuts',[(0,b'0',[(1,b'AppName',b'Existing game'),(2,b'flags',b'\x01\0\0\0')])])];path.write_bytes(encode(original))
            result=register(home/'APK-Revival',home);self.assertTrue(result['registered']);parsed=parse(path.read_bytes());self.assertEqual(parsed[0][2][0],original[0][2][0]);self.assertEqual(len(parsed[0][2]),2);self.assertTrue(register(home/'APK-Revival',home)['already_present']);self.assertEqual(pathlib.Path(result['backup']).read_bytes(),encode(original))
    def test_running_steam_is_not_modified(self):
        from apk_revival.launcher.steam import register
        with tempfile.TemporaryDirectory() as temp:
            home=pathlib.Path(temp);(home/'.steam').mkdir();(home/'.steam/steam.pid').write_text('123')
            with patch('apk_revival.launcher.steam.os.kill'):self.assertFalse(register(home/'APK-Revival',home)['registered'])
