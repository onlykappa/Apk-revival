"""ARM game support on x86 PCs: does a game need it, does Android have it, how to add it.

Most Android games ship native code for ARM phones only. On an x86 PC (such as the
Steam Deck) Android runs them through an ARM translation library. APK Revival
cannot ship those libraries, so it detects them and guides the user.
"""
from __future__ import annotations
import pathlib

ARM = ('arm64-v8a', 'armeabi-v7a', 'armeabi')
X86 = ('x86_64', 'x86')
TRANSLATORS = {'libndk_translation.so': 'libndk_translation', 'libhoudini.so': 'libhoudini'}
GUIDE_URL = 'https://github.com/casualsnek/waydroid_script'
# Errors starting with this let the launcher open the ARM setup guide.
ERROR_PREFIX = 'ARM support needed: '


def needs_arm(p):
    """True when the game only has ARM native code (it cannot run natively on x86)."""
    abis = ((p or {}).get('analysis') or {}).get('abis') or []
    return bool(abis) and not any(a in X86 for a in abis)


def android_status(abis, bridge=None):
    """Summarise Android's ARM support from ro.product.cpu.abilist and the native bridge."""
    abis = [a.strip() for a in (abis or []) if a and a.strip()]
    arm = [a for a in abis if a in ARM]
    translator = TRANSLATORS.get((bridge or '').strip())
    if arm and not any(a in X86 for a in abis):
        translator = translator or 'native ARM device'
    return {'known': bool(abis), 'arm': bool(arm), 'arm_abis': arm, 'translator': translator}


def compatible(p, status):
    """None if fine or unknown, otherwise a plain-language reason the game cannot start."""
    if not status or not status.get('known') or not needs_arm(p):
        return None
    if not status.get('arm'):
        return 'This game is built only for ARM phones, and your Android has no ARM support yet.'
    game = (p.get('analysis') or {}).get('abis') or []
    if not any(a in status['arm_abis'] or (a == 'armeabi' and 'armeabi-v7a' in status['arm_abis']) for a in game):
        return 'This game needs ' + ', '.join(game) + ' ARM support, but your Android provides only ' + ', '.join(status['arm_abis']) + '.'
    return None


def cpu_vendor(cpuinfo='/proc/cpuinfo'):
    try:
        text = pathlib.Path(cpuinfo).read_text(errors='replace')
    except OSError:
        return None
    return 'amd' if 'AuthenticAMD' in text else 'intel' if 'GenuineIntel' in text else None


def recommended_translator(vendor):
    # waydroid_script notes libndk performs better on AMD (the Steam Deck is AMD).
    return 'libhoudini' if vendor == 'intel' else 'libndk'


def guide(vendor=None):
    """Steps to add ARM support to Waydroid with the community waydroid_script tool."""
    library = recommended_translator(vendor)
    commands = '\n'.join([
        'git clone https://github.com/casualsnek/waydroid_script',
        'cd waydroid_script',
        'python3 -m venv venv',
        'venv/bin/pip install -r requirements.txt',
        f'sudo venv/bin/python3 main.py install {library}',
    ])
    why = ('Your PC has an AMD processor, so libndk is recommended.' if vendor == 'amd' else
           'Your PC has an Intel processor, so libhoudini is recommended.' if vendor == 'intel' else
           'libndk is recommended on AMD processors (including the Steam Deck) and libhoudini on Intel.')
    return {'library': library, 'commands': commands, 'why': why, 'url': GUIDE_URL, 'steps': [
        'Open a terminal (Konsole on the Steam Deck, in Desktop Mode).',
        'Run the commands below. The last one asks for your administrator password; the tool also needs lzip installed.',
        'Restart Android: in APK Revival, stop any game, then use Setup > Start Android (or restart your PC).',
        'Come back to Setup > ARM game support and choose Check ARM support.',
    ], 'note': 'waydroid_script is a community tool and is not part of APK Revival. It adds translation libraries taken from vendor Android images; it is tested on Android 11 images.'}
