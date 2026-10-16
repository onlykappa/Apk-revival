import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from apk_revival.launcher import metadata


class MergedMetadataTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'),'Requires user-owned original APK')
    def test_original_meego_label_and_icon_resolve_without_changing_apk(self):
        import hashlib
        apk=Path(os.environ['APKR_MEEGO_APK']);before=hashlib.sha256(apk.read_bytes()).hexdigest()
        label=metadata.resolve_label(apk,'@0x7f040022')
        self.assertIn('Meego',label)
        member=metadata.find_icon(apk,{'icon':'@0x7f020001'})
        self.assertIsNotNone(member)
        with zipfile.ZipFile(apk) as z:self.assertTrue(z.read(member).startswith(b'\x89PNG'))
        self.assertEqual(hashlib.sha256(apk.read_bytes()).hexdigest(),before)

    def test_missing_and_malformed_resource_tables_fall_back_safely(self):
        for contents in (None,b'bad',b'\x02\x00'+b'\xff'*14):
            with tempfile.TemporaryDirectory() as temp:
                apk=Path(temp)/'fixture.apk'
                with zipfile.ZipFile(apk,'w') as z:
                    z.writestr('res/mipmap-hdpi/ic_launcher.png',b'icon')
                    if contents is not None:z.writestr('resources.arsc',contents)
                self.assertIsNone(metadata.resolve_label(apk,'@0x7f040022'))
                self.assertEqual(metadata.find_icon(apk,{'icon':'@0x7f020001'}),'res/mipmap-hdpi/ic_launcher.png')

    def test_game_details_preserve_unknown_android_api_and_existing_profile(self):
        import copy
        p={'analysis':{'metadata':{'package':'example.game','min_sdk':'37','target_sdk':'36','version_name':'1.32'},'abis':['armeabi']},'restoration':{'path':'local_backend'},'inputs':[]}
        before=copy.deepcopy(p);rows=dict(metadata.details(p))
        self.assertEqual(rows['Requires'],'API 37 or newer')
        self.assertEqual(rows['Architecture'],'ARM (legacy)')
        self.assertEqual(rows['Method'],'Local game service')
        self.assertEqual(p,before)
