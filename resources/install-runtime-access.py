"""One-time administrator installation, never called by Play automatically."""
import os
import pathlib
import pwd
import re
import stat
import subprocess
import sys
import tempfile

MARKER = b'APK Revival fixed main-profile runtime helper v1'
ETC = pathlib.Path('/etc')


def policy(username):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        raise ValueError('Unsupported account name')
    actions = ('probe', 'preflight', 'mount', 'start-container', 'post-start')
    commands = ', '.join('/etc/apk-revival/runtime-helper ' + action for action in actions)
    return ('# APK Revival dedicated runtime access v1\n'
            + username + ' ALL=(root) NOPASSWD: NOSETENV: ' + commands + '\n').encode()


def safe_directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Expected a root-owned directory without group/world write access: ' + str(path))


def atomic_file(path, content, mode):
    fd, temporary = tempfile.mkstemp(prefix='.apk-revival-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def install(username):
    if os.geteuid() != 0:
        raise PermissionError('One-time administrator authorization is required')
    account = pwd.getpwnam(username)
    if account.pw_uid == 0 or not account.pw_dir.startswith('/home/'):
        raise ValueError('Expected an existing non-root home account')
    invoking = os.environ.get('PKEXEC_UID', os.environ.get('SUDO_UID'))
    if invoking is None or int(invoking) != account.pw_uid:
        raise ValueError('The account must match the invoking administrator')
    rules = policy(username)
    for required in ('/usr/bin/waydroid-mount', '/usr/bin/waydroid-firewall', '/usr/lib/steamos-waydroid/shared-folder.sh', '/usr/lib/steamos-waydroid/waydroid-profile.sh'):
        p = pathlib.Path(required)
        info = p.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Runtime dependency is not protected: ' + required)
    content = pathlib.Path(__file__).with_name('apk-revival-runtime-helper').read_bytes()
    if MARKER not in content or not content.startswith(b'#!/bin/bash\n'):
        raise ValueError('Dedicated helper content is missing')
    subprocess.run(['/bin/bash', '-n'], input=content, check=True, env={'PATH': '/usr/bin:/bin'})
    etc = ETC
    sudoers = etc / 'sudoers.d'
    safe_directory(etc)
    safe_directory(sudoers)
    # Validate sudo syntax before touching either installed file.
    with tempfile.NamedTemporaryFile(prefix='apkr-sudoers-') as check:
        check.write(rules); check.flush()
        subprocess.run(['/usr/bin/visudo', '-cf', check.name], check=True, env={'PATH': '/usr/bin:/bin'})
    folder = etc / 'apk-revival'
    folder.mkdir(mode=0o755, exist_ok=True)
    safe_directory(folder)
    helper = folder / 'runtime-helper'
    rule_file = sudoers / 'apk-revival-runtime'
    for target, marker in ((helper, MARKER), (rule_file, b'# APK Revival dedicated runtime access v1')):
        if target.is_symlink(): raise ValueError('Refusing a symlink: ' + str(target))
        if target.exists():
            info = target.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or marker not in target.read_bytes():
                raise ValueError('Refusing to replace an unrelated or unprotected file: ' + str(target))
    previous = {p: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode)) if p.exists() else None for p in (helper, rule_file)}
    try:
        atomic_file(helper, content, 0o755)
        atomic_file(rule_file, rules, 0o440)
        subprocess.run(['/usr/bin/visudo', '-cf', '/etc/sudoers'], check=True, env={'PATH': '/usr/bin:/bin'})
    except BaseException:
        for p, old in previous.items():
            if old is None: p.unlink(missing_ok=True)
            else: atomic_file(p, *old)
        raise
    print('Installed dedicated password-free runtime access. No runtime was restarted and no game data changed.')


if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('Expected the invoking account name')
    install(sys.argv[1])
