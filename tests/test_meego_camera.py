import copy
import os
import struct
import unittest
import zipfile
from unittest.mock import Mock, patch

from apk_revival.launcher.service import Launcher
from apk_revival.meego import camera, frame_pacing
from apk_revival.util import RevivalError


class CameraRepairTests(unittest.TestCase):
    def test_only_active_guest_modes_select_the_faster_timer(self):
        def mode(hz):
            return 'mActiveSfDisplayMode=DisplayMode{id=0, refreshRate='+str(hz)+', group=-1}'
        cases = [('', 60), ('supportedModes [{fps=90.0}]', 60),
                 (mode(60), 60), (mode(90), 90), (mode(89.99), 90),
                 (mode(120), 60), (mode('90oops'), 60),
                 (mode(90)+'\n'+mode(60), 60),
                 (mode(90)+'\n'+mode(90), 90)]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(frame_pacing.active_timer_hz(text), expected)

    def test_old_null_and_different_rate_plans_need_an_update(self):
        for old in ({}, {'plan': None}, {'plan': {}},
                    {'plan': {'meego_client_fixes': {'revision': 0, 'timer_hz': 90}}}):
            self.assertFalse(camera.prepared(old, 90))
        current = {'plan': {'meego_client_fixes': camera.configuration(90)}}
        self.assertTrue(camera.prepared(current, 90))
        self.assertFalse(camera.prepared(current, 60))

    def test_unreviewed_library_is_rejected_even_at_60_hz(self):
        with self.assertRaises(RevivalError):
            camera.patches(b'unknown', 60)

    @unittest.skipUnless(os.getenv('APKR_MEEGO_APK'), 'Requires privately owned original APK')
    def test_real_input_patch_rejects_to_return_without_touching_dispatch(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            original = archive.read('lib/armeabi/libverde.so')
        for hz in (60, 90):
            patches = camera.patches(original, hz)
            self.assertEqual(len(patches), 1 if hz == 60 else 2)
            changed = bytearray(original)
            for item in patches:
                offset = item['offset']
                old, new = bytes.fromhex(item['old']), bytes.fromhex(item['new'])
                self.assertEqual(original[offset:offset+len(old)], old)
                self.assertEqual(len(new), len(old))
                changed[offset:offset+len(new)] = new
            offset = camera.MOVE_REJECTION_OFFSET
            old, = struct.unpack_from('<I', original, offset)
            new, = struct.unpack_from('<I', changed, offset)
            self.assertEqual(old >> 24, 0x1A)  # BNE, retain condition
            self.assertEqual(new >> 24, 0x1A)
            self.assertEqual(offset+8+((old & 0xFFFFFF) << 2), 0x50C330)
            self.assertEqual(offset+8+((new & 0xFFFFFF) << 2), 0x50C34C)
            self.assertEqual(changed[0x50C318:0x50C354], original[0x50C318:0x50C354])
            self.assertEqual(len(changed), len(original))
            with self.assertRaises(RevivalError):
                camera.patches(changed, hz)


class CameraMigrationTests(unittest.TestCase):
    def setUp(self):
        self.launcher = object.__new__(Launcher)
        self.launcher.store = Mock()
        self.runtime = Mock()
        self.runtime.shell.return_value = 'mActiveSfDisplayMode=DisplayMode{refreshRate=90.0, group=-1}'
        self.ctx = Mock()
        self.profile = {'id': 'a'*24, 'adapter': 'meego-1.32', 'runtime': {},
                        'restoration': {'path': 'local_backend', 'artifact': 'old.apk'}}

    def test_matching_client_is_reused_without_preparation(self):
        self.profile['restoration']['plan'] = {'meego_client_fixes': camera.configuration(90)}
        with patch('apk_revival.restoration.Restorer') as restorer:
            self.assertIs(self.launcher.before_play(self.profile, self.runtime, self.ctx), self.profile)
            restorer.assert_not_called()
        self.launcher.store.save.assert_not_called()
        self.assertEqual(self.runtime.shell.call_args.kwargs['timeout'], 5)

    def test_old_client_updates_once_and_probe_failure_uses_60(self):
        self.runtime.shell.side_effect = RevivalError('display timeout')
        prepared = copy.deepcopy(self.profile)
        prepared['restoration']['artifact'] = 'new.apk'
        with patch('apk_revival.launcher.tools_setup.health', return_value={'preparation_ready': True}), \
                patch('apk_revival.restoration.Restorer') as restorer:
            restorer.return_value.prepare.return_value = prepared
            result = self.launcher.before_play(self.profile, self.runtime, self.ctx)
        restorer.return_value.prepare.assert_called_once_with(self.profile['id'], 'local_backend', progress=self.ctx.step)
        self.assertEqual(self.profile['runtime']['meego_timer_hz'], 60)
        self.assertEqual(result['restoration']['artifact'], 'new.apk')

    def test_missing_tools_keep_the_old_artifact_and_profile(self):
        before = copy.deepcopy(self.profile)
        with patch('apk_revival.launcher.tools_setup.health', return_value={'preparation_ready': False}), \
                patch('apk_revival.restoration.Restorer') as restorer:
            with self.assertRaisesRegex(RevivalError, 'previous APK and saves'):
                self.launcher.before_play(self.profile, self.runtime, self.ctx)
            restorer.assert_not_called()
        self.assertEqual(self.profile, before)
        self.launcher.store.save.assert_not_called()
