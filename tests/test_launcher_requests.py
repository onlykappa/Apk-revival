"""Library queue behavior without Qt, live runtime, or user saves."""
import hashlib
import json
import os
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apk_revival.launcher import requests as r
from apk_revival.store import Store
from apk_revival.util import RevivalError, atomic_json


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.game = 'a' * 24
        atomic_json(self.store.directory(self.game) / 'profile.json',
                    {'id': self.game, 'schema_version': 1})
        self.now = 10000
        self.clock = patch.object(r.time, 'time', return_value=self.now)
        self.clock.start()
        self.window = SimpleNamespace(service=SimpleNamespace(store=self.store),
                                      worker=None, monitor_worker=None)
        self.called = []
        self.reply = None
        self.accept = True
        def run(value, reply):
            self.called.append(value)
            self.reply = reply
            return self.accept
        self.window.run_library_request = run
        self.window.raise_ = lambda: None
        self.window.activateWindow = lambda: None
        self.window.open_apk = lambda path: self.called.append(path)

    def tearDown(self):
        self.clock.stop()
        self.temp.cleanup()

    def result(self, queued):
        return json.loads(pathlib.Path(queued['result_file']).read_text())

    def test_play_validates_known_profile_and_queue_paths_are_private(self):
        queued = r.enqueue(self.store, 'play', self.game)
        value = json.loads(pathlib.Path(queued['request_file']).read_text())
        self.assertEqual(value['game'], self.game)
        self.assertEqual(value['expires_at'], self.now + 300)
        self.assertEqual(self.result(queued)['state'], 'queued')
        for file in ('request_file', 'result_file'):
            path = pathlib.Path(queued[file])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(r.process_requests(self.window), 1)
        self.assertEqual(self.called[0]['action'], 'play')
        self.assertFalse(pathlib.Path(queued['request_file']).exists())
        self.assertEqual(self.result(queued)['state'], 'running')
        job = 'b' * 32
        self.reply(state='succeeded', job_id=job)
        self.assertEqual(self.result(queued)['job_id'], job)
        self.assertEqual(r.process_requests(self.window), 0)

    def test_worker_monitor_and_handler_busy_keep_request_until_idle(self):
        queued = r.enqueue(self.store, 'stop')
        for attribute in ('worker', 'monitor_worker'):
            setattr(self.window, attribute, object())
            self.assertEqual(r.process_requests(self.window), 0)
            self.assertEqual(self.called, [])
            self.assertTrue(pathlib.Path(queued['request_file']).exists())
            setattr(self.window, attribute, None)
        self.accept = False
        self.assertEqual(r.process_requests(self.window), 0)
        self.assertEqual(self.result(queued)['state'], 'queued')
        self.assertTrue(pathlib.Path(queued['request_file']).exists())
        self.accept = True
        self.assertEqual(r.process_requests(self.window), 1)

    def test_synchronous_completion_is_not_overwritten_and_delayed_reply_is_bound(self):
        first = r.enqueue(self.store, 'stop')
        second = r.enqueue(self.store, 'restart-runtime')
        callbacks = {}
        def run(value, reply):
            callbacks[value['id']] = reply
            reply({'state': 'succeeded', 'job_id': 'c' * 32})
            return True
        self.window.run_library_request = run
        self.assertEqual(r.process_requests(self.window), 2)
        self.assertEqual(self.result(first)['state'], 'succeeded')
        self.assertEqual(self.result(second)['state'], 'succeeded')
        callbacks[first['id']](state='failed', error='First job only')
        self.assertEqual(self.result(first)['error'], 'First job only')
        self.assertIsNone(self.result(second)['error'])

    def test_enqueue_rejects_unknown_action_game_traversal_and_missing_profile(self):
        for action, game in [('shell', None), ('play', '../' + 'a' * 21),
                             ('play', 'b' * 24), ('stop', self.game)]:
            with self.assertRaises(RevivalError):
                r.enqueue(self.store, action, game)
        self.assertFalse((self.store.root / 'open-requests').exists())

    def test_consumption_revalidates_profile_and_reports_expired_requests(self):
        queued = r.enqueue(self.store, 'play', self.game)
        (self.store.directory(self.game) / 'profile.json').unlink()
        self.assertEqual(r.process_requests(self.window), 1)
        self.assertEqual(self.result(queued)['state'], 'failed')
        self.assertEqual(self.called, [])
        queued = r.enqueue(self.store, 'quit')
        with patch.object(r.time, 'time', return_value=self.now + 300):
            self.assertEqual(r.process_requests(self.window), 1)
        self.assertIn('expired', self.result(queued)['error'])
        self.assertEqual(self.called, [])

    def test_result_paths_and_ids_cannot_be_supplied_by_request_or_callback(self):
        queued = r.enqueue(self.store, 'stop')
        value = json.loads(pathlib.Path(queued['request_file']).read_text())
        external = self.store.root / 'outside.json'
        value.update(id='../outside', result_file=str(external))
        atomic_json(queued['request_file'], value)
        self.assertEqual(r.process_requests(self.window), 1)
        self.assertEqual(self.result(queued)['id'], queued['id'])
        self.assertEqual(self.result(queued)['state'], 'failed')
        self.assertFalse(external.exists())
        queued = r.enqueue(self.store, 'stop')
        r.process_requests(self.window)
        self.reply({'state': 'succeeded', 'result_file': str(external), 'id': '../outside'})
        self.assertEqual(self.result(queued)['id'], queued['id'])
        self.assertFalse(external.exists())

    def test_legacy_dolphin_import_keeps_file_check_and_waits_for_idle(self):
        apk = self.store.root / 'game.APK'
        apk.write_bytes(b'privately owned fixture')
        path = self.store.root / 'open-requests' / ('d' * 32 + '.json')
        atomic_json(path, {'apk': str(apk)})
        os.utime(path, (self.now, self.now))
        self.window.monitor_worker = object()
        self.assertEqual(r.process_requests(self.window), 0)
        self.assertTrue(path.exists())
        self.window.monitor_worker = None
        self.assertEqual(r.process_requests(self.window), 1)
        self.assertEqual(self.called, [str(apk)])
        atomic_json(path, {'apk': str(self.store.root / 'missing.apk')})
        os.utime(path, (self.now, self.now))
        self.assertEqual(r.process_requests(self.window), 1)
        self.assertEqual(self.called, [str(apk)])
        result = json.loads((self.store.root / 'open-results' / path.name).read_text())
        self.assertEqual(result['state'], 'failed')

    def test_symlink_bad_filename_and_oversized_requests_never_dispatch(self):
        requests = self.store.root / 'open-requests'
        requests.mkdir()
        external = self.store.root / 'keep.json'
        external.write_text('{"action":"quit"}')
        link = requests / ('e' * 32 + '.json')
        link.symlink_to(external)
        bad = requests / 'untrusted-name.json'
        bad.write_text('{"action":"quit"}')
        big = requests / ('f' * 32 + '.json')
        big.write_bytes(b' ' * (r.MAX_BYTES + 1))
        self.assertEqual(r.process_requests(self.window), 3)
        self.assertTrue(external.exists())
        self.assertEqual(self.called, [])
        safe_id = hashlib.sha256(bad.name.encode()).hexdigest()[:32]
        self.assertEqual(json.loads((self.store.root / 'open-results' / (safe_id + '.json')).read_text())['state'], 'failed')

    def test_queue_and_per_poll_are_bounded(self):
        for _ in range(r.MAX_PENDING):
            r.enqueue(self.store, 'stop')
        with self.assertRaises(RevivalError):
            r.enqueue(self.store, 'stop')
        self.assertEqual(r.process_requests(self.window), r.MAX_PER_POLL)
        self.assertEqual(len(list((self.store.root / 'open-requests').glob('*.json'))), r.MAX_PENDING - r.MAX_PER_POLL)

    def test_play_then_stop_keep_queue_order_independent_of_uuid_sort(self):
        with patch.object(r.uuid, 'uuid4', return_value=SimpleNamespace(hex='f' * 32)):
            first = r.enqueue(self.store, 'play', self.game)
        with patch.object(r.uuid, 'uuid4', return_value=SimpleNamespace(hex='a' * 32)):
            second = r.enqueue(self.store, 'stop')
        os.utime(first['request_file'], (1, 1))
        os.utime(second['request_file'], (2, 2))
        self.assertEqual(r.process_requests(self.window), 2)
        self.assertEqual([v['action'] for v in self.called], ['play', 'stop'])

    def test_window_handler_failure_is_reported_without_repeated_dispatch(self):
        queued = r.enqueue(self.store, 'restart-runtime')
        def run(*args):
            raise RevivalError('Runtime is unavailable')
        self.window.run_library_request = run
        self.assertEqual(r.process_requests(self.window), 1)
        self.assertEqual(self.result(queued)['state'], 'failed')
        self.assertIn('unavailable', self.result(queued)['error'])
        self.assertEqual(r.process_requests(self.window), 0)


if __name__ == '__main__':
    unittest.main()
