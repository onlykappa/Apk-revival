import os,pathlib,stat,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from apk_revival.launcher.runtime_setup import RuntimeManager
from apk_revival.util import RevivalError,external_env,command

class RuntimeSetupTests(unittest.TestCase):
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
