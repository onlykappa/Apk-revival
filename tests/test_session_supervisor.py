import os,pathlib,subprocess,tempfile,unittest

class SessionSupervisorTests(unittest.TestCase):
    def test_disconnected_display_stops_owned_session_and_exits(self):
        with tempfile.TemporaryDirectory() as temp:
            home=pathlib.Path(temp);bin_dir=home/'bin';bin_dir.mkdir()
            randr=home/'.local/opt/steamos-waydroid/current/bin/wlr-randr';randr.parent.mkdir(parents=True)
            randr.write_text('''#!/bin/bash
if [[ "$1" == --output ]]; then echo "$*" > "$HOME/mode"; exit 0; fi
if [[ ! -f "$HOME/queried" ]]; then touch "$HOME/queried"; printf 'OTHER-OUTPUT "private"\\n  Enabled: yes\\n'; exit 0; fi
exit 1
''');randr.chmod(0o755)
            waydroid=bin_dir/'waydroid';waydroid.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$HOME/commands"
if [[ "$*" == 'session start' ]]; then
  while [[ ! -f "$HOME/stopped" ]]; do sleep 0.02; done
elif [[ "$*" == 'session stop' ]]; then touch "$HOME/stopped"; fi
''');waydroid.chmod(0o755)
            sudo=bin_dir/'sudo';sudo.write_text('#!/bin/bash\nprintf "%s\\n" "$*" > "$HOME/startup-request"\n');sudo.chmod(0o755)
            script=pathlib.Path(__file__).resolve().parents[1]/'resources/managed-waydroid-session.sh'
            env=dict(os.environ,HOME=temp,PATH=str(bin_dir)+':/usr/bin:/bin')
            result=subprocess.run(['/bin/bash',str(script)],env=env,capture_output=True,text=True,timeout=12)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((home/'stopped').exists());self.assertIn('session stop',(home/'commands').read_text())
            self.assertIn('--output OTHER-OUTPUT',(home/'mode').read_text())
            self.assertIn('managed-waydroid-startup.sh',(home/'startup-request').read_text())
            self.assertNotIn('init',(home/'commands').read_text())
    def test_no_broad_security_or_performance_tweaks_in_private_startup(self):
        script=(pathlib.Path(__file__).resolve().parents[1]/'resources/managed-waydroid-startup.sh').read_text()
        # Inspect executable lines, not comments describing what was removed.
        lines='\n'.join(line for line in script.splitlines() if not line.lstrip().startswith('#'))
        for forbidden in ('chmod','sysctl','setupwizard','shizuku','rm -','init '):self.assertNotIn(forbidden,lines)
        self.assertIn('mount_waydroid_share_when_ready',lines)
