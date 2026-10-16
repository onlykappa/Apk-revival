import os
import struct
import unittest
import zipfile

from apk_revival.meego import frame_pacing as pacing
from apk_revival.util import RevivalError


class TimerProfileTests(unittest.TestCase):
    def test_default_restoration_does_not_change_the_game_timer(self):
        self.assertEqual(pacing.patches(b'not needed for the default profile'), [])

    def test_unknown_profiles_and_libraries_are_rejected(self):
        for hz in (0, 120, '90', True):
            with self.assertRaises(RevivalError):
                pacing.patches(b'unknown', hz)
        with self.assertRaises(RevivalError):
            pacing.patches(b'unknown', 90)

    @unittest.skipUnless(os.getenv('APKR_MEEGO_APK'), 'Requires the privately owned original APK')
    def test_real_patch_is_bounded_and_branches_to_the_existing_double_divide(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            original = archive.read('lib/armeabi/libverde.so')
        patch, = pacing.patches(original, 90)
        offset = patch['offset']
        old, new = bytes.fromhex(patch['old']), bytes.fromhex(patch['new'])
        self.assertEqual(len(old), 52)
        self.assertEqual(len(new), len(old))
        self.assertEqual(original[offset:offset + len(old)], old)
        changed = original[:offset] + new + original[offset + len(old):]
        self.assertEqual(len(changed), len(original))
        self.assertEqual(changed[:offset], original[:offset])
        self.assertEqual(changed[offset + len(old):], original[offset + len(old):])
        branch, = struct.unpack_from('<I', new, 16)
        self.assertEqual(branch >> 24, 0xEB)
        self.assertEqual(offset + 16 + 8 + ((branch & 0xFFFFFF) << 2), 0xA59D38)
        with self.assertRaises(RevivalError):
            pacing.patches(changed, 90)


if __name__ == '__main__':
    unittest.main()
