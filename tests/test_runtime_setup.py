import os,pathlib,stat,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from apk_revival.launcher.runtime_setup import RuntimeManager
from apk_revival.util import RevivalError,external_env,command

class RuntimeSetupTests(unittest.TestCase):
    def test_frozen_runtime_does_not_inject_app_qt_plugins_into_konsole(self):
        internal='/home/deck/.local/share/apk-revival-app/_internal'
        qt=internal+'/PySide6/Qt/plugins'
        source={
            'LD_LIBRARY_PATH':internal,
            'QT_QPA_PLATFORM_PLUGIN_PATH':qt+'/platforms',
            'QT_PLUGIN_PATH':qt+':/usr/lib/qt6/plugins',
            'QT_QPA_FONTDIR':internal+'/PySide6/Qt/lib/fonts',
            'QML2_IMPORT_PATH':internal+'/PySide6/Qt/qml',
            'QTWEBENGINEPROCESS_PATH':internal+'/PySide6/Qt/libexec/QtWebEngineProcess',
            'QT_QPA_PLATFORM':'offscreen',
            'WAYLAND_DISPLAY':'wayland-1',
            'DISPLAY':':0',
        }
        with patch('apk_revival.util.sys.frozen',True,create=True),patch.dict(os.environ,source,clear=True):
            env=RuntimeManager().environment()
        for key in ('QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_FONTDIR',
                    'QML2_IMPORT_PATH','QTWEBENGINEPROCESS_PATH',
                    'QT_QPA_PLATFORM','LD_LIBRARY_PATH'):
            self.assertNotIn(key,env)
        self.assertEqual(env['QT_PLUGIN_PATH'],'/usr/lib/qt6/plugins')
        self.assertEqual(env['WAYLAND_DISPLAY'],'wayland-1')
        self.assertEqual(env['DISPLAY'],':0')

    def test_source_development_keeps_qt_environment(self):
        original={'QT_QPA_PLATFORM_PLUGIN_PATH':'/tmp/custom/qt',
                  'QT_QPA_PLATFORM':'offscreen'}
        with patch('apk_revival.util.sys.frozen',False,create=True):
            self.assertEqual(external_env(original),original)

    def test_frozen_runtime_strips_nested_update_private_openssl(self):
        staged='/home/deck/.cache/apk-revival/updates/staged-abc/APK-Revival/_internal'
        previous='/home/deck/.local/share/apk-revival-app/_internal'
        source={
            'LD_LIBRARY_PATH':staged+':/usr/local/lib',
            'LD_LIBRARY_PATH_ORIG':previous+':/usr/local/lib:/opt/vendor/lib',
            'WAYLAND_DISPLAY':'wayland-1',
        }
        with patch('apk_revival.util.sys.frozen',True,create=True),patch.dict(os.environ,source,clear=True):
            env=RuntimeManager().environment()
        self.assertEqual(env['LD_LIBRARY_PATH'],'/usr/local/lib:/opt/vendor/lib')
        self.assertNotIn('LD_LIBRARY_PATH_ORIG',env)
        self.assertEqual(env['WAYLAND_DISPLAY'],'wayland-1')

    def test_host_command_never_inherits_packaged_libcrypto(self):
        private='/home/deck/.cache/apk-revival/updates/staged-abc/APK-Revival/_internal'
        with patch('apk_revival.util.sys.frozen',True,create=True),patch.dict(os.environ,{
                'LD_LIBRARY_PATH':private,'LD_LIBRARY_PATH_ORIG':private,
            },clear=True),patch('apk_revival.util.subprocess.run') as execute:
            from subprocess import CompletedProcess
            execute.return_value=CompletedProcess(['/usr/bin/systemctl'],0,'active\\n','')
            self.assertEqual(command(['/usr/bin/systemctl','is-active','waydroid-container.service']),'active\\n')
        env=execute.call_args.kwargs['env']
        self.assertNotIn('LD_LIBRARY_PATH',env)
        self.assertNotIn('LD_LIBRARY_PATH_ORIG',env)

    def test_source_python_environment_remains_unchanged(self):
        original={'LD_LIBRARY_PATH':'/opt/custom/lib','LD_LIBRARY_PATH_ORIG':'original'}
        with patch('apk_revival.util.sys.frozen',False,create=True):
            clean=external_env(original)
        self.assertEqual(clean,original)

    def test_frozen_host_konsole_does_not_inherit_private_qt_plugins(self):
        private='/home/deck/.local/share/apk-revival-app/_internal/PySide6/Qt/plugins'
        previous='/home/deck/.cache/apk-revival/updates/staged-x/APK-Revival/_internal/PySide6/Qt/qml'
        source={'QT_QPA_PLATFORM_PLUGIN_PATH':private,
                'QT_PLUGIN_PATH':private+':/usr/lib/qt6/plugins',
                'QML2_IMPORT_PATH':previous,
                'QT_QPA_FONTDIR':private,
                'QT_QPA_PLATFORM':'offscreen',
                'WAYLAND_DISPLAY':'wayland-1',
                'DISPLAY':':0'}
        with patch('apk_revival.util.sys.frozen',True,create=True),patch.dict(os.environ,source,clear=True):
            env=RuntimeManager().environment()
        self.assertNotIn('QT_QPA_PLATFORM_PLUGIN_PATH',env)
        self.assertNotIn('QML2_IMPORT_PATH',env)
        self.assertNotIn('QT_QPA_FONTDIR',env)
        self.assertNotIn('QT_QPA_PLATFORM',env)
        self.assertEqual(env['QT_PLUGIN_PATH'],'/usr/lib/qt6/plugins')
        self.assertEqual(env['WAYLAND_DISPLAY'],'wayland-1')
        self.assertEqual(env['DISPLAY'],':0')

    def test_play_starts_existing_steamos_bundle_and_waits_for_adb(self):
        with tempfile.TemporaryDirectory() as temp,patch('pathlib.Path.home',return_value=pathlib.Path(temp)):
            base=pathlib.Path(temp)/'Android_Waydroid';base.mkdir()
            (base/'waydroid.img').write_bytes(b'existing image')
            launcher=base/'Android_Waydroid_Cage.sh';launcher.write_text('#!/bin/bash\\n');launcher.chmod(0o755)
            manager=RuntimeManager()
            states=iter([
                {'ready':False,'waydroid':True,'session':'STOPPED','service':'inactive','container':'unknown','devices':[]},
                {'ready':False,'waydroid':True,'session':'RUNNING','service':'active','container':'RUNNING','devices':[]},
                {'ready':True,'waydroid':True,'session':'RUNNING','service':'active','container':'RUNNING','devices':[{'serial':'192.168.240.112:5555','state':'device'}]},
            ])
            manager.discover=lambda **kwargs:next(states)
            with patch.object(manager,'start_steam_bundle') as start,patch('apk_revival.launcher.runtime_setup.time.sleep'):
                self.assertEqual(manager.ensure(),'192.168.240.112:5555')
            start.assert_called_once()
            self.assertTrue((base/'waydroid.img').is_file())

    def test_connected_android_never_restarts_cage_or_prepares_again(self):
        manager=RuntimeManager()
        manager.discover=lambda **kw:{'ready':True,'waydroid':True,'session':'RUNNING','devices':[{'state':'device','serial':'192.168.240.112:5555'}]}
        with patch.object(manager,'start_steam_bundle') as start:
            self.assertEqual(manager.ensure('192.168.240.112:5555'),'192.168.240.112:5555')
        start.assert_not_called()

    def test_steamos_bundle_uses_konsole_only_if_sudo_prompt_required(self):
        with tempfile.TemporaryDirectory() as temp,patch('pathlib.Path.home',return_value=pathlib.Path(temp)):
            base=pathlib.Path(temp)/'Android_Waydroid';base.mkdir()
            (base/'waydroid.img').write_bytes(b'preserve')
            launcher=base/'Android_Waydroid_Cage.sh';launcher.write_text('#!/bin/bash\\n');launcher.chmod(0o755)
            manager=RuntimeManager()
            with patch('apk_revival.launcher.runtime_setup.command',side_effect=RevivalError('sudo authorization needed')),patch(
                'apk_revival.launcher.runtime_setup.tool',side_effect=lambda name:'/usr/bin/'+name
            ),patch('apk_revival.launcher.runtime_setup.subprocess.Popen') as opened:
                manager.start_steam_bundle()
            cmd=opened.call_args.args[0]
            self.assertEqual(cmd,['/usr/bin/konsole','--separate','-e',str(launcher)])
            self.assertEqual(opened.call_args.kwargs['cwd'],str(base))
            self.assertIn('password',manager.last_start_note)
            self.assertEqual((base/'waydroid.img').read_bytes(),b'preserve')

    def test_cached_authorization_starts_bundle_without_terminal(self):
        with tempfile.TemporaryDirectory() as temp,patch('pathlib.Path.home',return_value=pathlib.Path(temp)):
            base=pathlib.Path(temp)/'Android_Waydroid';base.mkdir()
            (base/'waydroid.img').write_bytes(b'preserve')
            launcher=base/'Android_Waydroid_Cage.sh';launcher.write_text('#!/bin/bash\\n');launcher.chmod(0o755)
            manager=RuntimeManager()
            with patch('apk_revival.launcher.runtime_setup.command',return_value='') as check,patch(
                'apk_revival.launcher.runtime_setup.tool',return_value='/usr/bin/sudo'
            ),patch('apk_revival.launcher.runtime_setup.subprocess.Popen') as opened:
                manager.start_steam_bundle()
            self.assertEqual(opened.call_args.args[0],[str(launcher)])
            self.assertEqual(check.call_args.args[0],['/usr/bin/sudo','-n','-v'])

    def test_start_container_reuses_bundle_not_raw_systemctl(self):
        manager=RuntimeManager()
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/home/deck/Android_Waydroid/Android_Waydroid_Cage.sh')),patch.object(manager,'ensure') as connect,patch.object(manager,'discover') as discover:
            result=manager.start_container_authorized()
        connect.assert_called_once()
        discover.assert_not_called()
        self.assertEqual(result,manager.last)

    def run_command(self,args,**kwargs):
        if args[-1]=='status':return 'Session:        STOPPED\nVendor type:    MAINLINE\n'
        if '--property=ActiveState' in args:return 'active\n'
        if 'devices' in args:return 'List of devices attached\n'
        return ''
    def test_stopped_session_does_not_imply_stopped_service(self):
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:n),patch('apk_revival.launcher.runtime_setup.command',side_effect=self.run_command):
            info=RuntimeManager().discover()
        self.assertEqual(info['session'],'STOPPED');self.assertEqual(info['container'],'unknown');self.assertEqual(info['service'],'active');self.assertFalse(info['ready'])
    def test_active_service_start_is_explained_without_elevation(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'ready':False,'service':'active','container':'unknown'}
        with patch('apk_revival.launcher.runtime_setup.command') as call:manager.start_container_authorized()
        call.assert_not_called();self.assertIn('already running',manager.last_start_note)
    def test_steamos_authorization_opens_terminal_and_checks_result(self):
        manager=RuntimeManager();states=iter([{'steam_os':True,'service':'inactive','container':'unknown'},{'steam_os':True,'service':'active','container':'unknown'}]);manager.discover=lambda **kw:next(states)
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:'/usr/bin/'+n),patch('apk_revival.launcher.runtime_setup.command') as call:manager.start_container_authorized()
        self.assertEqual(call.call_args.args[0],['/usr/bin/konsole','--separate','-e','/usr/bin/sudo','/usr/bin/systemctl','start','waydroid-container.service'])
        self.assertIn('started',manager.last_start_note)
    def test_failed_konsole_reports_manual_recovery_without_modifying_container(self):
        manager=RuntimeManager()
        manager.discover=lambda **kw:{'steam_os':True,'service':'inactive','container':'unknown'}
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:'/usr/bin/'+n),patch(
            'apk_revival.launcher.runtime_setup.command',side_effect=RevivalError('/usr/bin/konsole failed (-6)')
        ) as cmd:
            with self.assertRaisesRegex(RevivalError,'sudo systemctl start waydroid-container.service'):
                manager.start_container_authorized()
        cmd.assert_called_once()
        self.assertIn('konsole',cmd.call_args.args[0][0])

    def test_failed_authorization_does_not_report_success(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'steam_os':False,'service':'inactive','container':'unknown'}
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:n),patch('apk_revival.launcher.runtime_setup.command'):
            with self.assertRaisesRegex(RevivalError,'did not become active'):manager.start_container_authorized()
    def test_existing_wayland_socket_is_reused_without_compositor(self):
        with tempfile.TemporaryDirectory() as temp:
            socket_path=pathlib.Path(temp)/'wayland-3';socket_path.touch();original=pathlib.Path.stat
            def metadata(path,*args,**kwargs):
                if path==socket_path:return SimpleNamespace(st_mode=stat.S_IFSOCK,st_uid=os.getuid())
                return original(path,*args,**kwargs)
            with patch.dict(os.environ,{'XDG_RUNTIME_DIR':temp},clear=True),patch('pathlib.Path.stat',metadata):
                manager=RuntimeManager();self.assertEqual(manager.environment()['WAYLAND_DISPLAY'],'wayland-3');manager.ensure_display();self.assertIsNone(manager.compositor_process)
    def test_existing_running_session_does_not_require_host_display(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'ready':False,'devices':[],'waydroid':True,'service':'active','container':'unknown','session':'RUNNING','ip':'192.168.240.112','errors':['connection refused']}
        with patch('apk_revival.launcher.runtime_setup.time.monotonic',side_effect=[0,31]),patch.object(manager,'ensure_display') as display:
            with self.assertRaisesRegex(RevivalError,'Guest IP'):manager.ensure()
        display.assert_not_called()
    def test_unauthorized_guest_needs_human_approval(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'ready':False,'devices':[{'serial':'guest','state':'unauthorized'}],'waydroid':False,'errors':[]}
        with self.assertRaisesRegex(RevivalError,'ADB authorization'):manager.ensure()
