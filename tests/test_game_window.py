import os
import unittest
from unittest.mock import patch

from apk_revival.launcher.game_window import KdeGameWindow, fullscreen_script
from apk_revival.util import RevivalError


class GameWindowTests(unittest.TestCase):
    def test_real_javascript_only_fullscreens_exact_normal_game_and_new_windows(self):
        # The minimal packaged launcher omits QtQml. Exercise the actual JS
        # using the Deck's existing Duktape library, with no app dependency.
        import ctypes
        import ctypes.util
        library=ctypes.util.find_library('duktape')
        if not library:self.skipTest('JavaScript runtime unavailable')
        js=ctypes.CDLL(library)
        js.duk_create_heap.argtypes=[ctypes.c_void_p]*5
        js.duk_create_heap.restype=ctypes.c_void_p
        js.duk_get_global_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        js.duk_push_lstring.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t]
        js.duk_pcall.argtypes=[ctypes.c_void_p,ctypes.c_int]
        js.duk_get_boolean.argtypes=[ctypes.c_void_p,ctypes.c_int]
        js.duk_destroy_heap.argtypes=[ctypes.c_void_p]
        context=js.duk_create_heap(None,None,None,None,None)
        self.assertTrue(context)
        self.addCleanup(js.duk_destroy_heap,context)
        def evaluate(source):
            payload=source.encode()
            js.duk_get_global_string(context,b'eval')
            js.duk_push_lstring(context,payload,len(payload))
            self.assertEqual(js.duk_pcall(context,1),0,'JavaScript execution failed')
            return bool(js.duk_get_boolean(context,-1))
        evaluate('''
            var matching = {resourceClass:'waydroid.ata.apkrv.meego', normalWindow:true, fullScreenable:true, fullScreen:false};
            var other = {resourceClass:'waydroid.other.game', normalWindow:true, fullScreenable:true, fullScreen:false};
            var dialog = {resourceClass:'waydroid.ata.apkrv.meego', normalWindow:false, fullScreenable:true, fullScreen:false};
            var added;
            var workspace = {windowList:function(){return [matching,other,dialog];},
                             windowAdded:{connect:function(callback){added=callback;}}};
        ''' + fullscreen_script('ata.apkrv.meego'))
        self.assertTrue(evaluate('matching.fullScreen && !other.fullScreen && !dialog.fullScreen'))
        self.assertTrue(evaluate('matching.fullScreen=false; matching.fullScreen === false'))
        self.assertTrue(evaluate('added(matching); matching.fullScreen'))

    def test_load_run_and_unload_are_scoped_and_remove_temporary_file(self):
        env={'XDG_CURRENT_DESKTOP':'KDE', 'XDG_SESSION_TYPE':'wayland'}
        with patch.dict(os.environ,env), patch('apk_revival.launcher.game_window.tool',return_value='/usr/bin/qdbus6'), patch('apk_revival.launcher.game_window.command',side_effect=['7','','true']) as command:
            window=KdeGameWindow()
            self.assertIn('Requested KDE fullscreen',window.start('game.example'))
            script=window.script
            self.assertEqual(script.stat().st_mode & 0o777,0o600)
            self.assertIn('waydroid.game.example',script.read_text())
            self.assertEqual(command.call_args_list[1].args[0][2],'/Scripting/Script7')
            window.stop()
            self.assertFalse(script.exists())
            self.assertIn('unloadScript',command.call_args.args[0][3])

    def test_gaming_mode_and_other_desktops_are_untouched(self):
        for desktop,session in [('gamescope','wayland'),('GNOME','wayland'),('KDE','x11')]:
            with patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':desktop,'XDG_SESSION_TYPE':session}),patch('apk_revival.launcher.game_window.command') as command:
                KdeGameWindow().start('game.example')
                command.assert_not_called()

    def test_unavailable_bus_is_nonfatal_and_cleans_up(self):
        with patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':'KDE','XDG_SESSION_TYPE':'wayland'}),patch('apk_revival.launcher.game_window.tool',return_value='qdbus6'),patch('apk_revival.launcher.game_window.command',side_effect=RevivalError('bus unavailable')):
            window=KdeGameWindow()
            self.assertIn('bus unavailable',window.start('game.example'))
            self.assertIsNone(window.script)
            self.assertIsNone(window.name)

    def test_package_cannot_inject_script(self):
        for invalid in ['*','Waydroid','game.example\";workspace.slotCloseWindow();','game.example\n']:
            with self.assertRaises(ValueError):fullscreen_script(invalid)

