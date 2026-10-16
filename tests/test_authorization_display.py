import os,pathlib,subprocess,tempfile,unittest
from unittest.mock import patch
from apk_revival.launcher.runtime_setup import RuntimeManager

ROOT=pathlib.Path(__file__).resolve().parents[1]

class AuthorizationDisplayTests(unittest.TestCase):
    def restored(self,extra):
        env={'PATH':'/usr/bin:/bin',**extra}
        # Exercise the shipped context helper without opening a password dialog.
        script='. "$1"; printf "%s\\n" "${WAYLAND_DISPLAY-unset}" "${DISPLAY-unset}" "${XAUTHORITY-unset}"'
        return subprocess.check_output(['/bin/sh','-c',script,'test',str(ROOT/'resources/waydroid-auth-display.sh')],env=env,text=True).splitlines()

    def test_private_android_display_is_replaced_by_actual_parent_context(self):
        self.assertEqual(self.restored({'APKR_AUTH_CONTEXT':'1','WAYLAND_DISPLAY':'private-android','DISPLAY':':99',
            'XAUTHORITY':'/private/auth','APKR_AUTH_WAYLAND_DISPLAY':'desktop-custom',
            'APKR_AUTH_DISPLAY':':7','APKR_AUTH_XAUTHORITY':'/parent/auth'}),['desktop-custom',':7','/parent/auth'])

    def test_wayland_only_parent_does_not_inherit_nested_x_display(self):
        self.assertEqual(self.restored({'APKR_AUTH_CONTEXT':'1','APKR_AUTH_WAYLAND_DISPLAY':'parent',
            'WAYLAND_DISPLAY':'private','DISPLAY':':99','XAUTHORITY':'/nested'}),['parent','unset','unset'])

    def test_direct_parent_authorization_without_marker_is_unchanged(self):
        self.assertEqual(self.restored({'WAYLAND_DISPLAY':'existing','DISPLAY':':2','XAUTHORITY':'/existing'}),['existing',':2','/existing'])

    def test_start_saves_parent_context_and_keeps_private_log_after_closing(self):
        with tempfile.TemporaryDirectory() as temp:
            manager=RuntimeManager(pathlib.Path(temp)/'runtime-state.json')
            with patch.object(manager,'environment',return_value={'WAYLAND_DISPLAY':'parent-special','DISPLAY':':4'}),patch('apk_revival.launcher.runtime_setup.subprocess.Popen') as start:
                manager.start_steam_bundle()
            env=start.call_args.kwargs['env']
            self.assertEqual(env['APKR_AUTH_WAYLAND_DISPLAY'],'parent-special')
            self.assertEqual(env['APKR_AUTH_DISPLAY'],':4');self.assertEqual(env['APKR_AUTH_XAUTHORITY'],'')
            manager.bundle_log.write(b'render failure\n');manager.bundle_log.close()
            self.assertEqual(manager.bundle_log_path.read_bytes(),b'render failure\n')
            self.assertEqual(manager.bundle_log_path.stat().st_mode&0o777,0o600)
