import tempfile,pathlib,json,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from apk_revival.launcher.input_diagnostics import frame_records,frame_summary,focused_package,collect,LABELS
from apk_revival.util import RevivalError

class InputDiagnosticTests(unittest.TestCase):
    def test_frame_delta_excludes_baseline_invalid_and_flagged_frames(self):
        header='Flags,IntendedVsync,FrameCompleted\n'
        before=header+'0,1000000,2000000\n'
        after=before+'0,3000000,13000000\n1,4000000,30000000\n0,5000000,4000000\n0,0,30000000\n0,6000000,9223372036854775807\n'
        result=frame_summary(before,after);self.assertEqual(result['new_frames'],1);self.assertEqual(result['median_ms'],10);self.assertIn('NOT touchscreen latency',result['metric'])
    def test_missing_native_frame_stats_are_unknown_not_zero_latency(self):
        result=frame_summary('No frames','No frames');self.assertEqual(result['new_frames'],0);self.assertIsNone(result['median_ms']);self.assertIsNone(result['p95_ms'])
    def test_duplicate_frame_records_count_once(self):
        text='Flags,IntendedVsync,FrameCompleted\n0,100,200\n0,100,200\n';self.assertEqual(len(frame_records(text)),1)
    def test_focus_uses_reported_package_not_assumed_settings_screen(self):
        self.assertEqual(focused_package('mCurrentFocus=Window{123 u0 ata.apkrv.meego/com.apportable.activity.VerdeActivity}'),'ata.apkrv.meego');self.assertIsNone(focused_package('mCurrentFocus=null'))
    def test_no_android_report_never_starts_runtime_or_uses_saved_ip(self):
        with tempfile.TemporaryDirectory() as temp:
            manager=Mock();manager.environment.return_value={};manager.discover.return_value={'ip':None,'devices':[]}
            launcher=SimpleNamespace(store=SimpleNamespace(root=pathlib.Path(temp)),active=None,runtime_manager=manager);context=Mock()
            with patch('apk_revival.launcher.input_diagnostics.command',side_effect=RevivalError('sandbox blocked')),patch('apk_revival.launcher.input_diagnostics.tool',side_effect=lambda name:name):result=collect(launcher,LABELS[0],context,duration=1,settle=0)
            self.assertFalse(result['android_captured']);manager.ensure.assert_not_called();manager.start_steam_bundle.assert_not_called();self.assertIsNone(result['report']['physical_touch_latency_ms']);self.assertEqual(result['report']['changes_applied'],[]);self.assertTrue((pathlib.Path(result['directory'])/'report.json').is_file())
    def test_guest_capture_does_not_mutate_settings_or_game(self):
        with tempfile.TemporaryDirectory() as temp:
            manager=Mock();manager.environment.return_value={};launcher=SimpleNamespace(store=SimpleNamespace(root=pathlib.Path(temp)),active={'kind':'android','serial':'current'},runtime_manager=manager)
            runtime=Mock();runtime.shell.side_effect=lambda *args,**kwargs:'mCurrentFocus=Window{x u0 ata.apkrv.meego/Activity}' if args[:3]==('dumpsys','window','windows') else '';runtime.adb.return_value=''
            with patch('apk_revival.launcher.input_diagnostics.command',return_value=''),patch('apk_revival.launcher.input_diagnostics.tool',side_effect=lambda name:name),patch('apk_revival.launcher.input_diagnostics.WaydroidRuntime',return_value=runtime),patch('apk_revival.launcher.input_diagnostics.time.sleep'):result=collect(launcher,LABELS[0],Mock(),duration=1,settle=0)
            self.assertTrue(result['android_captured']);self.assertFalse(result['report']['focus_changed']);self.assertEqual(result['report']['focused_android_package'],'ata.apkrv.meego')
            for call in runtime.shell.call_args_list:self.assertIn(call.args[0],('wm','getprop','dumpsys'));self.assertNotIn('reset',call.args);self.assertNotIn('set',call.args)
            runtime.stop.assert_not_called();runtime.install.assert_not_called();runtime.launch.assert_not_called()

    def test_android13_input_focus_fallback(self):
        input_text="FocusedWindows:\n    displayId=0, name='abc ata.apkrv.meego/com.apportable.activity.VerdeActivity'\n"
        self.assertEqual(focused_package('no focus field',input_text),'ata.apkrv.meego')
        self.assertIsNone(focused_package('no focus field','window layers for ata.apkrv.meego/Activity'))

    def test_surface_stats_reject_invalid_deduplicate_and_report_intervals(self):
        from apk_revival.launcher.input_diagnostics import surface_summary
        sample='16666666\n1 1000000 5\n2 1000000 6\n3 18000000 7\n4 51000000 8\n0 90000000 9\n1 9223372036854775807 1\n'
        result=surface_summary(sample)
        self.assertEqual(result['unique_presentations'],3);self.assertEqual(result['max_interval_ms'],33)
        self.assertEqual(result['retained_duration_ms'],50);self.assertIn('NOT physical touch latency',result['metric'])
        self.assertIsNone(surface_summary('No frames')['median_interval_ms'])

    def test_ack_wait_only_selected_game_connections(self):
        from apk_revival.launcher.input_diagnostics import input_summary
        sample="  Connections:\n    352: channelName='abc ata.apkrv.meego/Activity'\n      WaitQueue: length=2\n        MotionEvent, seq=1, wait=43ms\n        MotionEvent, seq=2, wait=6ms\n    353: channelName='other.game/Activity'\n      WaitQueue: length=1\n        MotionEvent, seq=3, wait=100ms\n"
        result=input_summary(sample,'ata.apkrv.meego')
        self.assertEqual(result['pending_motion_events'],2);self.assertEqual(result['max_ack_wait_ms'],43)
