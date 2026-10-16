"""Optional, one-time setup for the existing SteamOS main runtime."""
import os
import pathlib
import pwd
import sys
from ..util import RevivalError, command, external_env


def preflight_command(sudo):
    helper = pathlib.Path('/etc/apk-revival/runtime-helper')
    if helper.is_file() and os.access(helper, os.X_OK):
        return [sudo, '-n', str(helper), 'preflight']
    return [sudo, '-A', '/usr/bin/waydroid-mount', 'main', '--check-only']


def install(progress=lambda _: None):
    root = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parents[2])) / 'resources'
    script = root / 'install-runtime-access.py'
    helper = root / 'apk-revival-runtime-helper'
    if not script.is_file() or not helper.is_file():
        raise RevivalError('The dedicated runtime access installer is missing from this build.')
    if not pathlib.Path('/usr/bin/pkexec').is_file():
        raise RevivalError('SteamOS administrator authorization (pkexec) is unavailable.')
    progress('Waiting for one-time administrator authorization for dedicated runtime access')
    output = command(['/usr/bin/pkexec', '/usr/bin/python3', '-I', str(script), pwd.getpwuid(os.getuid()).pw_name],
                     timeout=120, env=external_env())
    progress('Dedicated runtime access installed; the running game was not restarted')
    return output
