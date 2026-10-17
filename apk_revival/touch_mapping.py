"""Controller-to-touch mapping: pin controller buttons to points on a game's screen.

Each mapped button press becomes an Android tap. Taps go through one persistent
`adb shell`, but Android's `input tap` still costs roughly 0.1-0.3 s, so this suits
menus, puzzle, card, idle and strategy games rather than fast action.
Mappings are stored per game as {button index: [x fraction, y fraction]}.
"""
from __future__ import annotations
import re, subprocess, threading
from .util import RevivalError, tool

# SDL game controller button indices.
BUTTONS = {0: 'A', 1: 'B', 2: 'X', 3: 'Y', 4: 'Back / View', 6: 'Start / Menu', 7: 'Left stick press',
           8: 'Right stick press', 9: 'Left bumper', 10: 'Right bumper', 11: 'D-pad up', 12: 'D-pad down',
           13: 'D-pad left', 14: 'D-pad right'}
SHORT = {0: 'A', 1: 'B', 2: 'X', 3: 'Y', 4: 'Bk', 6: 'St', 7: 'LS', 8: 'RS', 9: 'LB', 10: 'RB', 11: '↑', 12: '↓', 13: '←', 14: '→'}


def mapping(p):
    raw = ((p or {}).get('launcher') or {}).get('controls') or {}
    result = {}
    for key, point in raw.items():
        try:
            index, (x, y) = int(key), point
        except (TypeError, ValueError):
            continue
        if index in BUTTONS and 0 <= float(x) <= 1 and 0 <= float(y) <= 1:
            result[index] = (float(x), float(y))
    return result


def store_format(points):
    return {str(int(k)): [round(float(x), 4), round(float(y), 4)] for k, (x, y) in points.items() if int(k) in BUTTONS}


def screen_size(runtime):
    output = runtime.shell('wm', 'size', timeout=10)
    match = re.search(r'Override size:\s*(\d+)x(\d+)', output) or re.search(r'Physical size:\s*(\d+)x(\d+)', output)
    if not match:
        raise RevivalError('Android did not report its screen size, so controller taps are off for this session.')
    return int(match.group(1)), int(match.group(2))


def pixel(point, size):
    return int(round(point[0] * (size[0] - 1))), int(round(point[1] * (size[1] - 1)))


class TapSender:
    """One long-lived `adb shell`; each tap is a line written to it, off the UI thread."""
    def __init__(self, serial, popen=None):
        if not serial:
            raise RevivalError('No Android connection for controller taps.')
        self.process = (popen or subprocess.Popen)([tool('adb'), '-s', serial, 'shell'], stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        self.lock = threading.Lock()

    def tap(self, x, y):
        with self.lock:
            if self.process.poll() is not None:
                return False
            try:
                self.process.stdin.write(f'input tap {int(x)} {int(y)}\n')
                self.process.stdin.flush()
                return True
            except (OSError, ValueError):
                return False

    def close(self):
        with self.lock:
            try:
                if self.process.poll() is None:
                    self.process.stdin.write('exit\n');self.process.stdin.flush()
                    self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
