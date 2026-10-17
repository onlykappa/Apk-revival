"""Per-game network control in the Android guest: logging proxy, offline answers, blocking.

Modes (stored per game in launcher.network):
- 'normal': nothing changes.
- 'log': Android's HTTP proxy points at APK Revival, which records servers and relays.
- 'offline': the proxy answers for dead servers and a firewall rule blocks everything else.
- 'block': a firewall rule blocks the game's internet completely.
Firewall rules apply only to the game's Android user ID and always allow loopback,
so local game services reached through adb reverse keep working. Every change is
undone when the game stops; leftovers from a crash are removed before the next Play.
"""
from __future__ import annotations
import re
from .util import RevivalError

MODES = ('normal', 'log', 'offline', 'block')
LABELS = {'normal': 'Normal', 'log': 'Log connections (stays online)',
          'offline': 'Answer for dead servers (no internet)', 'block': 'Block internet'}
CHAIN = 'APKR_GAME_'


def mode(p):
    value = ((p or {}).get('launcher') or {}).get('network', 'normal')
    return value if value in MODES else 'normal'


def package_uid(runtime, package):
    output = runtime.shell('cmd', 'package', 'list', 'packages', '-U', package, timeout=15)
    for line in output.splitlines():
        match = re.fullmatch(r'package:(\S+)\s+uid:(\d+)', line.strip())
        if match and match.group(1) == package:
            return int(match.group(2))
    raise RevivalError('Could not find the game\'s Android user ID, so its network setting was not applied.')


def _root(runtime, script, timeout=30):
    return runtime.shell('su', '0', 'sh', '-c', script, timeout=timeout)


def block(runtime, uid):
    chain = CHAIN + str(int(uid))
    script = ' && '.join(f'{tool} -N {chain} && {tool} -A {chain} -o lo -j ACCEPT && {tool} -A {chain} -j REJECT && '
                         f'{tool} -I OUTPUT -m owner --uid-owner {int(uid)} -j {chain}' for tool in ('iptables', 'ip6tables'))
    try:
        _root(runtime, script)
    except RevivalError as error:
        unblock(runtime, uid)
        raise RevivalError('Blocking this game\'s internet needs Android root access, and it failed: ' + str(error)) from error
    return chain


def unblock(runtime, uid):
    chain = CHAIN + str(int(uid))
    script = '; '.join(f'{tool} -D OUTPUT -m owner --uid-owner {int(uid)} -j {chain} 2>/dev/null; {tool} -F {chain} 2>/dev/null; {tool} -X {chain} 2>/dev/null'
                       for tool in ('iptables', 'ip6tables')) + '; true'
    _root(runtime, script)


def remove_leftovers(runtime):
    """Delete firewall chains left behind if the launcher closed unexpectedly."""
    try:
        listing = _root(runtime, 'iptables -S 2>/dev/null; ip6tables -S 2>/dev/null', timeout=15)
    except RevivalError:
        return []
    uids = sorted({int(m) for m in re.findall(r'-N ' + CHAIN + r'(\d+)', listing)})
    for uid in uids:
        unblock(runtime, uid)
    return uids


def set_proxy(runtime, port):
    runtime.adb('reverse', f'tcp:{int(port)}', f'tcp:{int(port)}', timeout=10)
    runtime.shell('settings', 'put', 'global', 'http_proxy', f'127.0.0.1:{int(port)}', timeout=10)


def clear_proxy(runtime, port=None):
    """Reset Android's proxy; returns False if Android could not be reached."""
    cleared = False
    for command in (('settings', 'put', 'global', 'http_proxy', ':0'), ('settings', 'delete', 'global', 'http_proxy')):
        try:
            runtime.shell(*command, timeout=10)
            cleared = True
        except RevivalError:
            pass
    if port:
        try:
            runtime.adb('reverse', '--remove', f'tcp:{int(port)}', timeout=5)
        except RevivalError:
            pass
    return cleared
