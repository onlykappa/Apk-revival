"""Malformed library entries are isolated using temporary, self-authored data."""
import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from apk_revival.store import Store
from apk_revival.util import RevivalError, atomic_json, digest


class LibraryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.good_id = 'a' * 24
        self.bad_id = 'b' * 24
        self.profile = {'schema_version': 1, 'id': self.good_id, 'title': 'Healthy game',
                        'status': 'Imported', 'analysis': None, 'verification': [],
                        'restoration': {'path': None, 'artifact': None},
                        'inputs': [{'name': 'game.apk', 'stored_name': '0000_game.apk',
                                    'role': 'base_apk', 'sha256': 'a' * 64, 'size': 3}]}
        self.write(self.good_id, self.profile)

    def write(self, ident, value):
        path = self.store.directory(ident) / 'profile.json'
        atomic_json(path, value)
        return path

    def assert_bad_isolated(self, path):
        before = path.read_bytes()
        files_before = sorted(str(p.relative_to(self.store.root)) for p in self.store.root.rglob('*'))
        self.assertEqual(self.store.games(), [self.profile])
        self.assertEqual(len(self.store.last_library_errors), 1)
        self.assertEqual(self.store.last_library_errors[0]['file'], str(path))
        self.assertTrue(self.store.last_library_errors[0]['error'])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(str(p.relative_to(self.store.root)) for p in self.store.root.rglob('*')), files_before)

    def test_malformed_json_does_not_hide_healthy_entry_or_rewrite_any_file(self):
        path = self.write(self.bad_id, {})
        path.write_bytes(b'{ malformed')
        self.assert_bad_isolated(path)

    def test_nonobject_and_id_mismatch_profiles_are_isolated(self):
        for value in ([], None, 5, {**self.profile, 'id': self.good_id}):
            with self.subTest(value=value):
                self.assert_bad_isolated(self.write(self.bad_id, value))

    def test_bad_ui_structures_are_isolated(self):
        variants = [{'status': {}}, {'status': 'Unknown'}, {'title': []},
                    {'inputs': 'bad'}, {'inputs': [None]}, {'restoration': []},
                    {'analysis': []}, {'launcher': {'apk': []}},
                    {'launcher': {'apk': {'icon': []}}}, {'verification': [None]},
                    {'schema_version': True}]
        for change in variants:
            with self.subTest(change=change):
                bad = {**copy.deepcopy(self.profile), 'id': self.bad_id, **change}
                self.assert_bad_isolated(self.write(self.bad_id, bad))

    def test_missing_profile_and_read_race_are_reported(self):
        directory = self.store.directory(self.bad_id)
        directory.mkdir(parents=True)
        self.assertEqual(self.store.games(), [self.profile])
        self.assertEqual(self.store.last_library_errors[0]['file'], str(directory / 'profile.json'))
        self.assertFalse((directory / 'profile.json').exists())
        path = self.write(self.bad_id, {**self.profile, 'id': self.bad_id})
        from apk_revival.util import read_json
        def disappearing(candidate):
            if candidate == path:
                raise FileNotFoundError('Synthetic read race')
            return read_json(candidate)
        with patch('apk_revival.store.read_json', side_effect=disappearing):
            self.assertEqual(self.store.games(), [self.profile])
            self.assertIn('Synthetic read race', self.store.last_library_errors[0]['error'])

    def test_listing_never_hashes_originals_but_load_still_detects_changes(self):
        original = self.store.directory(self.good_id) / 'originals' / '0000_game.apk'
        original.parent.mkdir()
        original.write_bytes(b'apk')
        self.profile['inputs'][0]['sha256'] = digest(original)
        self.write(self.good_id, self.profile)
        self.assertEqual(self.store.load(self.good_id), self.profile)
        original.write_bytes(b'changed')
        with self.assertRaisesRegex(RevivalError, 'Original input hash changed'):
            self.store.load(self.good_id)
        with patch('apk_revival.store.digest', side_effect=AssertionError('Listing must not hash')):
            self.assertEqual(self.store.games(), [self.profile])

    def test_errors_reset_after_repair_and_empty_library_is_normal(self):
        bad = self.write(self.bad_id, [])
        self.store.games()
        self.assertTrue(self.store.last_library_errors)
        atomic_json(bad, {**self.profile, 'id': self.bad_id, 'title': 'Second healthy game'})
        self.assertEqual(len(self.store.games()), 2)
        self.assertEqual(self.store.last_library_errors, [])
        with tempfile.TemporaryDirectory() as empty:
            other = Store(empty)
            self.assertEqual(other.games(), [])
            self.assertEqual(other.last_library_errors, [])


if __name__ == '__main__':
    unittest.main()
