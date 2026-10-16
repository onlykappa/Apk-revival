import unittest
from unittest.mock import Mock
from apk_revival.launcher.runtime_setup import ManagedAndroid

class GamePresentationTests(unittest.TestCase):
    def test_scope_and_restore_existing_null_policy(self):
        runtime=ManagedAndroid('guest');runtime.shell=Mock(side_effect=['null*','','immersive.full=game.example',''])
        runtime.game_presentation('game.example');runtime.restore_presentation()
        self.assertEqual(runtime.shell.call_args_list[1].args,('settings','put','global','policy_control','immersive.full=game.example'))
        self.assertEqual(runtime.shell.call_args_list[-1].args,('settings','put','global','policy_control','null*'))
    def test_custom_controls_and_policy_are_preserved(self):
        runtime=ManagedAndroid('guest');runtime.shell=Mock(return_value='immersive.status=other.game')
        runtime.game_presentation('game.example');runtime.restore_presentation();self.assertEqual(runtime.shell.call_count,1)
    def test_external_policy_change_is_not_overwritten_on_stop(self):
        runtime=ManagedAndroid('guest');runtime.shell=Mock(side_effect=['null','','custom.new.policy'])
        runtime.game_presentation('game.example');runtime.restore_presentation();self.assertEqual(runtime.shell.call_count,3)
    def test_missing_original_setting_is_deleted_on_restore(self):
        runtime=ManagedAndroid('guest');runtime.shell=Mock(side_effect=['null','','immersive.full=game.example',''])
        runtime.game_presentation('game.example');runtime.restore_presentation()
        self.assertEqual(runtime.shell.call_args_list[-1].args,('settings','delete','global','policy_control'))
    def test_launch_wakes_discovered_guest_after_install_before_activity(self):
        from unittest.mock import patch
        from apk_revival.runtime import WaydroidRuntime
        runtime=ManagedAndroid('192.168.240.112:5555');runtime.package='game.example';runtime.shell=Mock(side_effect=['null*','','123'])
        profile={'restoration':{},'analysis':{'metadata':{'package':'game.example'}}}
        info={'ip':'192.168.240.112','container':'FROZEN'}
        with patch('apk_revival.launcher.runtime_setup.RuntimeManager') as manager,patch.object(WaydroidRuntime,'launch') as launch:
            manager.return_value.discover.return_value=info
            self.assertEqual(runtime.launch(profile),'123')
        manager.return_value.wake_runtime.assert_called_once();self.assertEqual(manager.return_value.wake_runtime.call_args.args[0],info)
        launch.assert_called_once_with(profile)
    def test_launching_explicit_phone_does_not_wake_another_guest(self):
        from unittest.mock import patch
        from apk_revival.runtime import WaydroidRuntime
        runtime=ManagedAndroid('phone');runtime.package='game.example';runtime.shell=Mock(side_effect=['custom-policy','123'])
        profile={'restoration':{},'analysis':{'metadata':{'package':'game.example'}}}
        with patch('apk_revival.launcher.runtime_setup.RuntimeManager') as manager,patch.object(WaydroidRuntime,'launch'):
            manager.return_value.discover.return_value={'ip':'192.168.240.112','container':'FROZEN'}
            runtime.launch(profile)
        manager.return_value.wake_runtime.assert_not_called()
