import importlib.util
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

from apk_revival.launcher import runtime_access

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime_access_installer', ROOT/'resources/install-runtime-access.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RuntimeAccessTests(unittest.TestCase):
    def test_policy_passes_real_visudo_and_grants_only_fixed_main_actions(self):
        rules = installer.policy('deck').decode()
        expected = {'/etc/apk-revival/runtime-helper '+a for a in ('probe','preflight','mount','start-container','post-start')}
        grants = rules.split('NOSETENV: ',1)[1].strip().split(', ')
        self.assertEqual(set(grants), expected)
        self.assertNotIn('*', rules)
        for unsafe in ('root', 'deck ALL=(ALL) ALL\n', '../deck', 'deck;id'):
            if unsafe == 'root':continue
            with self.assertRaises(ValueError):installer.policy(unsafe)
        with tempfile.NamedTemporaryFile() as f:
            f.write(rules.encode());f.flush()
            # SteamOS ships /usr/bin/visudo; Debian/Ubuntu CI runners keep it in /usr/sbin.
            visudo = next((p for p in ('/usr/bin/visudo','/usr/sbin/visudo') if os.path.exists(p)), None)
            if not visudo:self.skipTest('visudo is not installed')
            checked = subprocess.run([visudo,'-cf',f.name],capture_output=True,text=True)
            self.assertEqual(checked.returncode,0,checked.stderr)

    def test_installer_needs_real_administrator_and_matching_account(self):
        with patch.object(installer.os,'geteuid',return_value=1000):
            with self.assertRaises(PermissionError):installer.install('deck')
        with patch.object(installer.os,'geteuid',return_value=0),patch.dict(os.environ,{'PKEXEC_UID':'99999'}):
            with self.assertRaises(ValueError):installer.install(pwd.getpwuid(os.getuid()).pw_name)

    def test_config_validation_failure_rolls_back_only_its_own_new_files(self):
        account = pwd.getpwuid(os.getuid())
        with tempfile.TemporaryDirectory() as temp:
            etc = Path(temp)/'etc';etc.mkdir();(etc/'sudoers.d').mkdir()
            sentinel = etc/'sudoers.d/unrelated';sentinel.write_text('keep this configuration')
            real_stat = Path.stat
            def protected_dependencies(path, *args, **kwargs):
                if str(path).startswith('/usr/'):
                    return Mock(st_uid=0,st_mode=0o100755)
                return real_stat(path,*args,**kwargs)
            def validate(args, **kwargs):
                if args[-1]=='/etc/sudoers':raise subprocess.CalledProcessError(1,args)
                return subprocess.CompletedProcess(args,0)
            with patch.object(installer,'ETC',etc),patch.object(installer.os,'geteuid',return_value=0),patch.dict(os.environ,{'PKEXEC_UID':str(account.pw_uid)}),patch.object(installer,'safe_directory'),patch.object(Path,'stat',protected_dependencies),patch.object(installer.subprocess,'run',side_effect=validate) as run:
                with self.assertRaises(subprocess.CalledProcessError):installer.install(account.pw_name)
            self.assertFalse((etc/'apk-revival/runtime-helper').exists())
            self.assertFalse((etc/'sudoers.d/apk-revival-runtime').exists())
            self.assertFalse((etc/'sudoers.d'/installer.RULE_NAME).exists())
            self.assertEqual(sentinel.read_text(),'keep this configuration')
            self.assertTrue(all(c.args[0][0] in ('/bin/bash','/usr/bin/visudo') for c in run.call_args_list))

    def test_success_requires_uncached_probe_as_invoking_user_and_late_rule(self):
        self.assertGreater(installer.RULE_NAME,'zzzzzzzz-waydroid')
        self.assertGreater(installer.RULE_NAME,'wheel')
        account=pwd.getpwuid(os.getuid())
        with tempfile.TemporaryDirectory() as temp:
            etc=Path(temp)/'etc';etc.mkdir();(etc/'sudoers.d').mkdir()
            real_stat=Path.stat
            def protected(path,*args,**kwargs):
                if str(path).startswith('/usr/'):return Mock(st_uid=0,st_mode=0o100755)
                return real_stat(path,*args,**kwargs)
            def execute(args,**kwargs):
                return subprocess.CompletedProcess(args,0,'apk-revival-runtime-v1\n','')
            with patch.object(installer,'ETC',etc),patch.object(installer.os,'geteuid',return_value=0),patch.dict(os.environ,{'PKEXEC_UID':str(account.pw_uid)}),patch.object(installer,'safe_directory'),patch.object(Path,'stat',protected),patch.object(installer.subprocess,'run',side_effect=execute) as run:
                installer.install(account.pw_name)
            probe=run.call_args.args[0]
            self.assertEqual(probe[:8],['/usr/bin/runuser','-u',account.pw_name,'--','/usr/bin/sudo','-k','-n','--'])
            self.assertEqual(probe[-1],'probe')
            self.assertEqual(run.call_args.kwargs['timeout'],15)
            self.assertTrue((etc/'sudoers.d'/installer.RULE_NAME).is_file())
            self.assertFalse((etc/'sudoers.d/apk-revival-runtime').exists())

    def test_effective_access_failure_rolls_back_even_when_visudo_passes(self):
        account=pwd.getpwuid(os.getuid())
        with tempfile.TemporaryDirectory() as temp:
            etc=Path(temp)/'etc';etc.mkdir();(etc/'sudoers.d').mkdir()
            sentinel=etc/'sudoers.d/wheel';sentinel.write_text('unrelated host policy')
            real_stat=Path.stat
            def protected(path,*args,**kwargs):
                if str(path).startswith('/usr/'):return Mock(st_uid=0,st_mode=0o100755)
                return real_stat(path,*args,**kwargs)
            def execute(args,**kwargs):
                if args[0]=='/usr/bin/runuser':raise subprocess.CalledProcessError(1,args,stderr='sudo: a password is required')
                return subprocess.CompletedProcess(args,0)
            with patch.object(installer,'ETC',etc),patch.object(installer.os,'geteuid',return_value=0),patch.dict(os.environ,{'PKEXEC_UID':str(account.pw_uid)}),patch.object(installer,'safe_directory'),patch.object(Path,'stat',protected),patch.object(installer.subprocess,'run',side_effect=execute):
                with self.assertRaises(subprocess.CalledProcessError):installer.install(account.pw_name)
            self.assertFalse((etc/'sudoers.d'/installer.RULE_NAME).exists())
            self.assertFalse((etc/'apk-revival/runtime-helper').exists())
            self.assertEqual(sentinel.read_text(),'unrelated host policy')

    def test_unsafe_directory_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);link=p/'link';link.symlink_to(p,target_is_directory=True)
            with self.assertRaises(ValueError):installer.safe_directory(link)
            p.chmod(0o777)
            with self.assertRaises(ValueError):installer.safe_directory(p)

    def test_installed_helper_uses_noninteractive_sudo_and_absent_helper_keeps_fallback(self):
        with patch.object(Path,'is_file',return_value=True),patch.object(os,'access',return_value=True):
            self.assertEqual(runtime_access.preflight_command('/usr/bin/sudo'),['/usr/bin/sudo','-n','/etc/apk-revival/runtime-helper','preflight'])
        with patch.object(Path,'is_file',return_value=False):
            self.assertEqual(runtime_access.preflight_command('/usr/bin/sudo'),['/usr/bin/sudo','-A','/usr/bin/waydroid-mount','main','--check-only'])

    def test_one_time_setup_uses_isolated_python_and_never_starts_runtime(self):
        with patch.object(Path,'is_file',return_value=True),patch.object(runtime_access,'command',return_value='configured') as run:
            self.assertEqual(runtime_access.install(),'configured')
        args=run.call_args.args[0]
        self.assertEqual(args[:3],['/usr/bin/pkexec','/usr/bin/python3','-I'])
        self.assertTrue(args[3].endswith('resources/install-runtime-access.py'))
        self.assertEqual(args[4],pwd.getpwuid(os.getuid()).pw_name)
        self.assertEqual(run.call_count,1)


class MergedLauncherTests(unittest.TestCase):
    def test_long_game_title_and_package_fit_details_at_deck_sizes(self):
        from PySide6.QtWidgets import QApplication
        from apk_revival.launcher.ui import Window
        from apk_revival.store import Store
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temp,patch.object(Window,'check_runtime'):
            w=Window(Store(Path(temp)/'data'));w.show()
            w.game_title.setText('0000_The+Meego_1.32_APKPure_Extended_Game_Name')
            w.show_metadata([('Package','com.example.'+'longpackagename'*8)])
            for width,height in [(1280,800),(1000,650)]:
                w.resize(width,height);app.processEvents();app.processEvents()
                self.assertLessEqual(w.details.width(),w.details_scroll.viewport().width())
            w.close();app.processEvents()

    def test_recovery_diagnostics_new_village_and_runtime_access_survive_redesign(self):
        from PySide6.QtWidgets import QApplication, QPushButton
        from apk_revival.launcher.ui import Window
        from apk_revival.store import Store
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temp,patch.object(Window,'check_runtime'):
            w=Window(Store(Path(temp)/'data'));w.show();app.processEvents();w.show_setup();app.processEvents()
            labels={b.text() for b in w.setup.findChildren(QPushButton)}
            self.assertTrue({'Restart Android','Capture input diagnostics','Enable password-free startup'}<=labels)
            self.assertEqual(w.active_page,'setup')
            w.close();app.processEvents()
