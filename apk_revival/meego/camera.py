"""Exact-library camera input repair and prepared-client revision tracking.

See evidence/camera-display-comparison/pinch-code-findings.md. This is an
unverified native repair; no changes to gesture thresholds or camera bounds.
"""
import hashlib

from ..util import RevivalError
from . import frame_pacing

REVISION = 1
MOVE_REJECTION_OFFSET = 0x50C314
MOVE_REJECTION_ORIGINAL = bytes.fromhex('0500001a')
# ARM BNE: reject to the existing return epilogue, bypassing timestamp stores.
# Original target 0x50c330; new target 0x50c34c. Accepted moves still dispatch
# and store their timestamp. The instruction/ABI remain ARMv5TE compatible.
MOVE_REJECTION_FIXED = bytes.fromhex('0c00001a')


def configuration(hz=60):
    frame_pacing.validate_hz(hz)
    from . import timer_mod, lifecycle_mod
    return {'revision': REVISION, 'timer_hz': hz, 'native_timer_mod': timer_mod.REVISION, 'native_lifecycle_mod': lifecycle_mod.REVISION}


def prepared(restoration, hz=60):
    expected = configuration(hz)
    plan = restoration.get('plan')
    return isinstance(plan, dict) and plan.get('meego_client_fixes') == expected


def patches(library, hz=60):
    configuration(hz)
    if (hashlib.sha256(library).hexdigest() != frame_pacing.LIBRARY_SHA256 or
            library[MOVE_REJECTION_OFFSET:MOVE_REJECTION_OFFSET + 4] != MOVE_REJECTION_ORIGINAL):
        raise RevivalError('Meego camera input repair requires the exact reviewed original library.')
    return [dict(offset=MOVE_REJECTION_OFFSET, old=MOVE_REJECTION_ORIGINAL.hex(),
                 new=MOVE_REJECTION_FIXED.hex(),
                 reason='Keep the last dispatched move timestamp when rejecting a closely spaced input event'),
            *frame_pacing.patches(library, hz)]
