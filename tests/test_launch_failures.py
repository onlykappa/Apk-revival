import pathlib,tempfile,json,unittest
from unittest.mock import Mock,patch
from apk_revival.util import RevivalError
from apk_revival.runtime import WaydroidRuntime
from apk_revival.launcher.jobs import Jobs
from apk_revival.launcher.service import Launcher
from apk_revival.store import Store
from types import SimpleNamespace

class LaunchFailureTests(unittest.TestCase):
    def test_action_notice_does_not_stop_the_running_game(self):
        with tempfile.TemporaryDirectory() as temp:
            launcher=Launcher(Store(temp));active={'game':'test','kind':'android'}
            launcher.active=active
            state=SimpleNamespace(take_action_notice=lambda:'Build or upgrade huts to make room for a baby.')
            launcher.android=SimpleNamespace(package='ata.apkrv.meego',shell=lambda *args,**kwargs:'123',backend=SimpleNamespace(thread=SimpleNamespace(is_alive=lambda:True),server=SimpleNamespace(state=state)))
            self.assertIn('huts',launcher.monitor());self.assertIs(launcher.active,active);self.assertIsNotNone(launcher.android)
    def test_launch_commands_and_cleanup_have_short_independent_bounds(self):
        runtime=WaydroidRuntime('guest');runtime.shell=Mock(side_effect=['game.example/.Main','Starting: Intent','123']);runtime.launch_progress=Mock()
        profile={'restoration':{},'analysis':{'metadata':{'package':'game.example'}}}
        with patch('apk_revival.runtime.command'),patch('apk_revival.runtime.tool',side_effect=lambda name:name):
            runtime.launch(profile)
        resolve,start,pid=runtime.shell.call_args_list
        self.assertEqual(resolve.kwargs['timeout'],8);self.assertEqual(start.kwargs['timeout'],10);self.assertNotIn('-W',start.args)
        self.assertEqual(pid.kwargs['timeout'],3);self.assertGreaterEqual(runtime.launch_progress.call_count,4)
        runtime.shell=Mock();runtime.adb=Mock();runtime.forward_port=1234;runtime.stop()
        self.assertEqual(runtime.shell.call_args.kwargs['timeout'],5);self.assertEqual(runtime.adb.call_args.kwargs['timeout'],3)
    def test_job_error_and_exact_stage_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=pathlib.Path(temp)/'job-logs';jobs=Jobs(directory)
            def run(ctx):ctx.step('Resolving the game activity');raise RevivalError('Command timed out after 8s: adb cmd package')
            with self.assertRaisesRegex(RevivalError,'timed out'):jobs.run('Play Meego',run)
            records=list(directory.glob('*.json'));self.assertEqual(len(records),1)
            saved=json.loads(records[0].read_text());self.assertEqual(saved['state'],'failed');self.assertEqual(saved['steps'][0]['state'],'failed');self.assertIn('8s',saved['error']);self.assertIsNotNone(saved['ended_at'])
    def test_log_write_failure_does_not_replace_operation_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            jobs=Jobs(pathlib.Path(temp)/'job-logs')
            with patch('apk_revival.launcher.jobs.atomic_json',side_effect=OSError('full')):
                with self.assertRaisesRegex(RevivalError,'original launch error'):jobs.run('Play',lambda ctx:(_ for _ in ()).throw(RevivalError('original launch error')))
            self.assertEqual(jobs.last_history_error,'full');self.assertIsNone(jobs.active)
