"""Per-game display settings applied in Android while the game plays, then restored.

size: 'default', 'smaller' or 'larger' scales Android's screen density, which makes
text and buttons smaller (more fits on screen) or larger. landscape: lock rotation
to landscape. Previous values are read first and put back when the game stops.
"""
from __future__ import annotations
import re
from .util import RevivalError

SIZES = {'default': 1.0, 'smaller': 0.8, 'larger': 1.25}
SIZE_LABELS = {'default': 'Default', 'smaller': 'Smaller (fits more)', 'larger': 'Larger'}


def settings(p):
    value = ((p or {}).get('launcher') or {}).get('display') or {}
    size = value.get('size') if value.get('size') in SIZES else 'default'
    return {'size': size, 'landscape': bool(value.get('landscape'))}


def _density(runtime):
    output = runtime.shell('wm', 'density', timeout=10)
    physical = re.search(r'Physical density:\s*(\d+)', output)
    override = re.search(r'Override density:\s*(\d+)', output)
    if not physical:
        raise RevivalError('Android did not report its screen density.')
    return int(physical.group(1)), int(override.group(1)) if override else None


def _landscape_rotation(runtime):
    """Rotation 0 is the display's natural orientation; Waydroid's is usually already landscape."""
    try:
        output = runtime.shell('wm', 'size', timeout=10)
    except RevivalError:
        return '0'
    match = re.search(r'Override size:\s*(\d+)x(\d+)', output) or re.search(r'Physical size:\s*(\d+)x(\d+)', output)
    return '1' if match and int(match.group(1)) < int(match.group(2)) else '0'


def apply(runtime, p, remember=None):
    """Apply a game's display settings; returns what is needed to restore, or None.

    All current values are read and passed to remember() before anything changes,
    so a failure part-way can still be undone.
    """
    chosen = settings(p)
    if chosen['size'] == 'default' and not chosen['landscape']:
        return None
    previous, physical = {}, None
    if chosen['size'] != 'default':
        physical, previous['density'] = _density(runtime)
    if chosen['landscape']:
        for key in ('accelerometer_rotation', 'user_rotation'):
            previous[key] = runtime.shell('settings', 'get', 'system', key, timeout=10).strip()
    if remember:
        remember(previous)
    if physical:
        runtime.shell('wm', 'density', str(max(80, int(physical * SIZES[chosen['size']]))), timeout=10)
    if chosen['landscape']:
        runtime.shell('settings', 'put', 'system', 'accelerometer_rotation', '0', timeout=10)
        runtime.shell('settings', 'put', 'system', 'user_rotation', _landscape_rotation(runtime), timeout=10)
    return previous


def restore(runtime, previous):
    if not previous:
        return
    if 'density' in previous:
        runtime.shell('wm', 'density', str(previous['density']) if previous['density'] else 'reset', timeout=10)
    for key in ('accelerometer_rotation', 'user_rotation'):
        if key in previous:
            value = previous[key]
            if value and value != 'null':
                runtime.shell('settings', 'put', 'system', key, value, timeout=10)
            else:
                runtime.shell('settings', 'delete', 'system', key, timeout=10)
