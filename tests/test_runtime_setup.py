import os,pathlib,stat,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from apk_revival.launcher.runtime_setup import RuntimeManager
from apk_revival.util import RevivalError,external_env,command

class RuntimeSetupTests(unittest.TestCase):
    def test_direct_kde_display_uses_native_protocol_not_wlr_management(self):
        manager=RuntimeManager()
        env={'WAYLAND_DISPLAY':'verified-parent-7','XDG_SESSION_TYPE':'wayland','XDG_CURRENT_DESKTOP':'KDE'}
        protocols="interface: 'wl_compositor', version: 6\ninterface: 'wl_output', version: 4\ninterface: 'xdg_wm_base', version: 6"
        with patch.object(manager,'environment',return_value=env),patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:n),patch('apk_revival.launcher.runtime_setup.command',return_value=protocols) as run:
            self.assertTrue(manager.check_managed_display({'wayland_display':'verified-parent-7'}))
        self.assertEqual(run.call_args.args[0],['wayland-info'])
        self.assertEqual(run.call_args.kwargs['env']['WAYLAND_DISPLAY'],'verified-parent-7')

    def test_unresponsive_parent_display_is_not_accepted(self):
        manager=RuntimeManager()
        env={'WAYLAND_DISPLAY':'parent','XDG_SESSION_TYPE':'wayland','XDG_CURRENT_DESKTOP':'KDE'}
        with patch.object(manager,'environment',return_value=env),patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:n),patch('apk_revival.launcher.runtime_setup.command',side_effect=RevivalError('Display connection timed out')):
            self.assertFalse(manager.check_managed_display({'wayland_display':'parent'}))

    def setUp(self):
        guest=patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=lambda *args,**kw:'1' if args[0]=='getprop' else 'package:/system/framework/framework-res.apk')
        guest.start();self.addCleanup(guest.stop)
    def test_restart_checks_profile_before_stopping_and_reuses_image(self):
        manager=RuntimeManager()
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing/launcher')),patch('apk_revival.launcher.runtime_setup.command') as run,patch.object(manager,'ensure',return_value='current:5555') as ensure:
            self.assertEqual(manager.restart_android(),'current:5555')
        commands=[call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][-3:],['/usr/bin/waydroid-mount','main','--check-only'])
        self.assertEqual(commands[1][-2:],['session','stop'])
        self.assertEqual(len(commands),2)
        ensure.assert_called_once_with(progress=unittest.mock.ANY,_allow_recovery=False)

    def test_rejected_profile_check_never_stops_android(self):
        manager=RuntimeManager()
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing/launcher')),patch('apk_revival.launcher.runtime_setup.command',side_effect=RevivalError('wrong profile')) as run,patch.object(manager,'ensure') as ensure:
            with self.assertRaises(RevivalError):manager.restart_android()
        self.assertEqual(run.call_count,1)
        ensure.assert_not_called()

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
                {'ip':'192.168.240.112','ready':True,'waydroid':True,'session':'RUNNING','service':'active','container':'RUNNING','devices':[{'serial':'192.168.240.112:5555','state':'device'}]},
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

    def test_steamos_bundle_uses_graphical_authorization(self):
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
            self.assertEqual(cmd[0],'/bin/bash');self.assertTrue(cmd[1].endswith('managed-waydroid.sh'))
            self.assertTrue(opened.call_args.kwargs['env']['SUDO_ASKPASS'].endswith('waydroid-askpass.sh'))
            self.assertIn('authorization',manager.last_start_note)
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
            self.assertEqual(opened.call_args.args[0][0],'/bin/bash');check.assert_not_called()

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
        manager=RuntimeManager();manager.steam_bundle_launcher=lambda:None;manager.discover=lambda **kw:{'ready':False,'service':'active','container':'unknown'}
        with patch('apk_revival.launcher.runtime_setup.command') as call:manager.start_container_authorized()
        call.assert_not_called();self.assertIn('already running',manager.last_start_note)
    def test_container_authorization_uses_polkit_and_checks_result(self):
        manager=RuntimeManager();manager.steam_bundle_launcher=lambda:None;states=iter([{'steam_os':True,'service':'inactive','container':'unknown'},{'steam_os':True,'service':'active','container':'unknown'}]);manager.discover=lambda **kw:next(states)
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:'/usr/bin/'+n),patch('apk_revival.launcher.runtime_setup.command') as call:manager.start_container_authorized()
        self.assertEqual(call.call_args.args[0],['/usr/bin/pkexec','/usr/bin/systemctl','start','waydroid-container.service'])
        self.assertIn('started',manager.last_start_note)
    def test_failed_polkit_reports_failure_without_modifying_container(self):
        manager=RuntimeManager()
        manager.steam_bundle_launcher=lambda:None
        manager.discover=lambda **kw:{'steam_os':True,'service':'inactive','container':'unknown'}
        with patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda n:'/usr/bin/'+n),patch(
            'apk_revival.launcher.runtime_setup.command',side_effect=RevivalError('/usr/bin/konsole failed (-6)')
        ) as cmd:
            with self.assertRaisesRegex(RevivalError,'failed'):
                manager.start_container_authorized()
        cmd.assert_called_once()
        self.assertIn('pkexec',cmd.call_args.args[0][0])

    def test_failed_authorization_does_not_report_success(self):
        manager=RuntimeManager();manager.steam_bundle_launcher=lambda:None;manager.discover=lambda **kw:{'steam_os':False,'service':'inactive','container':'unknown'}
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
            with self.assertRaisesRegex(RevivalError,'connection refused'):manager.ensure()
        display.assert_not_called()
    def test_unauthorized_guest_needs_human_approval(self):
        manager=RuntimeManager();manager.discover=lambda **kw:{'ready':False,'devices':[{'serial':'guest','state':'unauthorized'}],'waydroid':False,'errors':[]}
        with self.assertRaisesRegex(RevivalError,'ADB authorization'):manager.ensure()


class ManagedRecoveryTests(unittest.TestCase):
    def state(self):
        return {'ready':True,'waydroid':True,'ip':'192.168.240.112','session':'RUNNING','devices':[{'state':'device','serial':'192.168.240.112:5555'}]}
    def test_missing_display_recovers_once_before_installing(self):
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing')),patch.object(manager,'restart_android',return_value='new-ip:5555') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=lambda *args,**kwargs:'1' if args[0]=='getprop' else "Can't find service: SurfaceFlinger"),patch('apk_revival.launcher.runtime_setup.time.sleep'):
            self.assertEqual(manager.ensure(),'new-ip:5555')
        restart.assert_called_once()
    def test_recovery_failure_propagates_without_repeated_password_prompts(self):
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing')),patch.object(manager,'restart_android',side_effect=RevivalError('authorization cancelled')) as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=lambda *args,**kwargs:'1' if args[0]=='getprop' else "Can't find service: SurfaceFlinger"),patch('apk_revival.launcher.runtime_setup.time.sleep'):
            with self.assertRaisesRegex(RevivalError,'authorization cancelled'):manager.ensure()
        restart.assert_called_once()
    def test_recovery_disabled_second_failure_does_not_restart(self):
        import itertools
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        with patch.object(manager,'restart_android') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',return_value="Can't find service: SurfaceFlinger"),patch('apk_revival.launcher.runtime_setup.time.sleep'),patch('apk_revival.launcher.runtime_setup.time.monotonic',side_effect=itertools.count()):
            with self.assertRaisesRegex(RevivalError,'bounded to one'):manager.ensure(_allow_recovery=False)
        restart.assert_not_called()
    def test_manual_unrelated_device_is_never_restarted(self):
        import itertools
        manager=RuntimeManager();manager.discover=lambda **kwargs:{'ready':True,'waydroid':True,'session':'RUNNING','devices':[{'state':'device','serial':'phone'}]}
        with patch.object(manager,'restart_android') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',return_value="Can't find service: SurfaceFlinger"),patch('apk_revival.launcher.runtime_setup.time.sleep'),patch('apk_revival.launcher.runtime_setup.time.monotonic',side_effect=itertools.count()):
            with self.assertRaises(RevivalError):manager.ensure('phone')
        restart.assert_not_called()
    def test_boot_and_packages_do_not_prove_display_readiness(self):
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        def shell(*args,**kwargs):
            if args[0]=='getprop':return '1'
            if args[0]=='pm':return 'package:/system/framework/framework-res.apk'
            return "Can't find service: SurfaceFlinger"
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing')),patch.object(manager,'restart_android',return_value='recovered') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=shell),patch('apk_revival.launcher.runtime_setup.time.sleep'):
            self.assertEqual(manager.ensure(),'recovered')
        restart.assert_called_once()

    def test_empty_display_reply_requires_missing_input_and_window_before_recovery(self):
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        def shell(*args,**kwargs):
            if args[0]=='getprop':return '1'
            if args[0]=='service':return 'Found 2 services:\n0\tmanager: [IServiceManager]\n1\tmedia.player: [IMediaPlayer]'
            return ''
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing')),patch.object(manager,'restart_android',return_value='recovered') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=shell),patch('apk_revival.launcher.runtime_setup.time.sleep'):
            self.assertEqual(manager.ensure(),'recovered')
        restart.assert_called_once()
    def test_empty_or_permission_limited_service_list_is_not_recovery_evidence(self):
        import itertools
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        with patch.object(manager,'restart_android') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',return_value=''),patch('apk_revival.launcher.runtime_setup.time.sleep'),patch('apk_revival.launcher.runtime_setup.time.monotonic',side_effect=itertools.count()):
            with self.assertRaises(RevivalError):manager.ensure()
        restart.assert_not_called()

    def test_frozen_container_wakes_before_guest_readiness_checks(self):
        manager=RuntimeManager();frozen={**self.state(),'container':'FROZEN'};awake={**self.state(),'container':'RUNNING'}
        states=iter([frozen,awake]);manager.discover=lambda **kwargs:next(states)
        def shell(*args,**kwargs):
            return '1' if args[0]=='getprop' else 'Display 0' if args[0]=='dumpsys' else 'package:/system/framework/framework-res.apk'
        with patch('apk_revival.launcher.runtime_setup.command',return_value='method return') as command,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=shell),patch.object(manager,'restart_android') as restart:
            self.assertEqual(manager.ensure(),'192.168.240.112:5555')
        self.assertEqual(command.call_count,1);self.assertIn('id.waydro.ContainerManager.Unfreeze',command.call_args.args[0]);restart.assert_not_called()
    def test_boot_in_progress_is_not_restarted_for_initially_missing_display_services(self):
        import itertools
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        def shell(*args,**kwargs):return '0' if args[0]=='getprop' else "Can't find service: SurfaceFlinger"
        with patch.object(manager,'restart_android') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=shell),patch('apk_revival.launcher.runtime_setup.time.sleep'),patch('apk_revival.launcher.runtime_setup.time.monotonic',side_effect=itertools.count()):
            with self.assertRaises(RevivalError):manager.ensure()
        restart.assert_not_called()

    def test_dead_private_socket_recovers_before_any_guest_command(self):
        manager=RuntimeManager();state={**self.state(),'wayland_display':'actual-private'};manager.discover=lambda **kwargs:state
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing')),patch.object(manager,'check_managed_display',return_value=False),patch.object(manager,'restart_android',return_value='recovered') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell') as shell:
            self.assertEqual(manager.ensure(),'recovered')
        restart.assert_called_once();shell.assert_not_called()
    def test_display_probe_uses_reported_socket_with_short_timeout(self):
        manager=RuntimeManager()
        with patch('pathlib.Path.is_file',return_value=True),patch.object(manager,'environment',return_value={'WAYLAND_DISPLAY':'host-desktop','XDG_RUNTIME_DIR':'/run/user/1000'}),patch('apk_revival.launcher.runtime_setup.command',return_value='PRIVATE-OUTPUT "nested"\n  Enabled: yes\n') as run:
            self.assertTrue(manager.check_managed_display({'wayland_display':'discovered-private'}))
        self.assertEqual(run.call_args.kwargs['env']['WAYLAND_DISPLAY'],'discovered-private');self.assertEqual(run.call_args.kwargs['timeout'],2)
    def test_cached_layers_without_composer_do_not_pass_readiness(self):
        manager=RuntimeManager();manager.discover=lambda **kwargs:self.state()
        def shell(*args,**kwargs):
            if args[0]=='getprop':return '1'
            if args[0]=='dumpsys':return 'Display 0 name="stale"'
            if args[0]=='ps':return 'NAME\ninit\nsurfaceflinger\n'
            return 'package:/system/framework/framework-res.apk'
        with patch.object(manager,'steam_bundle_launcher',return_value=pathlib.Path('/existing')),patch.object(manager,'check_managed_display',return_value=True),patch.object(manager,'restart_android',return_value='recovered') as restart,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=shell),patch('apk_revival.launcher.runtime_setup.time.sleep'):
            self.assertEqual(manager.ensure(),'recovered')
        restart.assert_called_once()
