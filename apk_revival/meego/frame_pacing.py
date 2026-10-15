"""Display timer patch for the exact reviewed Meego ARMv5TE client.

This changes CADisplayLink's render timer, not the Android display mode or the
backend simulation clock. The original director calculates elapsed-time deltas.
Play selects 90 only from the active guest display mode; otherwise it uses 60.
The native 90-Hz change still requires device gameplay validation.
"""
import hashlib
import re

from ..util import RevivalError

LIBRARY_SHA256 = '6b1000dccb517635a51656dd0439f49052a361b9a2a905b3e21453c481b3dcf3'
TIMER_OFFSET = 0x52D370
ORIGINAL = bytes.fromhex('0130a0e14e18a0e30020a0e10000a0e30080a0e3011181e36ab214eb0130a0e1ff16a0e30020a0e10000a0e3031281e364b214eb')
# r0/r1 already hold double(frameInterval). Construct double(90) in r2/r3,
# divide once, restore r8=0 for NSTimer userInfo, retain the original exit ABI.
# All instructions remain ARMv5TE compatible. No MOVW/MOVT or new ISA required.
NINETY_HZ = bytes.fromhex('0020a0e30131a0e3563883e3023983e36cb214eb0080a0e30000a0e10000a0e10000a0e10000a0e10000a0e10000a0e10000a0e1')


def validate_hz(hz):
    if type(hz) is not int or hz not in (60, 90):
        raise RevivalError('Meego display timer must use the reviewed 60 or 90 Hz profile.')


def active_timer_hz(display_dump):
    """Use active Android modes only, never supported modes or host refresh.

    Missing/ambiguous/unsupported modes retain the original 60-Hz timer. A
    display change takes effect on the next Play, not mid-gesture.
    """
    modes = re.findall(r'mActiveSfDisplayMode\s*=\s*DisplayMode\{([^}\n]+)\}', display_dump)
    if not modes:
        return 60
    for mode in modes:
        rate = re.search(r'\brefreshRate\s*=\s*([0-9]+(?:\.[0-9]+)?)(?=\s*(?:,|$))', mode)
        if not rate or abs(float(rate.group(1)) - 90) > 0.5:
            return 60
    return 90


def patches(library, hz=60):
    validate_hz(hz)
    if hz == 60:
        return []
    if (hashlib.sha256(library).hexdigest() != LIBRARY_SHA256 or
            library[TIMER_OFFSET:TIMER_OFFSET + len(ORIGINAL)] != ORIGINAL):
        raise RevivalError('Meego display-timer patch requires the exact reviewed original library.')
    return [dict(offset=TIMER_OFFSET, old=ORIGINAL.hex(), new=NINETY_HZ.hex(),
                 reason='90 Hz CADisplayLink timer selected for an active 90 Hz Android display; preserve elapsed-time director updates')]
