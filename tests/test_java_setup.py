"""SDK scripts must find private Java even when SteamOS has no java in PATH."""
import os,pathlib,tempfile,unittest
from unittest.mock import patch
from apk_revival.launcher.tools_setup import configure
from apk_revival.util import command,tool

class JavaSetupTests(unittest.TestCase):
    def test_sdk_script_finds_private_java_without_system_install(self):
        with tempfile.TemporaryDirectory(prefix='java setup ') as temp,patch.dict(os.environ,{'PATH':'/usr/bin:/bin'},clear=True):
            root=pathlib.Path(temp);bin=root/'jre/bin';bin.mkdir(parents=True)
            for name in ['java','keytool']:
                path=bin/name;path.write_text('#!/bin/sh\nprintf "private-runtime-ok\\n"\n');path.chmod(0o755)
            sdk=root/'android-15';sdk.mkdir();signer=sdk/'apksigner';signer.write_text('#!/bin/sh\nexec java "$@"\n');signer.chmod(0o755)
            configure(root);self.assertEqual(command([tool('apksigner'),'version']).strip(),'private-runtime-ok')
            self.assertEqual(os.environ['JAVA_HOME'],str(root/'jre'));self.assertEqual(tool('java'),str(bin/'java'))
            configure(root);self.assertEqual(os.environ['PATH'].split(os.pathsep).count(str(bin)),1)
    def test_explicit_runtime_is_used_by_sdk_scripts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);binary=root/'custom/bin/java';binary.parent.mkdir(parents=True);binary.write_text('test')
            with patch.dict(os.environ,{'APKR_JAVA':str(binary),'PATH':'/usr/bin'},clear=True):
                configure(root);self.assertEqual(os.environ['JAVA_HOME'],str(root/'custom'));self.assertEqual(os.environ['PATH'].split(os.pathsep)[0],str(binary.parent))
