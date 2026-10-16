"""Session-scoped KDE fullscreen for the game being launched, not the desktop.

Waydroid's HWC advertises xdg app_id = 'waydroid.' + Android package.
Android immersive mode cannot remove KDE decorations or the desktop panel.
"""
import json
import os
import pathlib
import re
import tempfile
import uuid

from ..util import RevivalError, command, tool


def fullscreen_script(package):
    if not re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+', package):
        raise ValueError('Invalid Android package for fullscreen')
    return '''const gameClass = %s;
function openFullscreen(window) {
    if (String(window.resourceClass) === gameClass && window.normalWindow &&
        window.fullScreenable) {
        window.fullScreen = true;
    }
}
// Apply once on creation, not on every activation: users can leave fullscreen.
workspace.windowAdded.connect(openFullscreen);
workspace.windowList().forEach(openFullscreen);
''' % json.dumps('waydroid.' + package)


class KdeGameWindow:
    def __init__(self):
        self.name = None
        self.script = None
        self.qdbus = None

    def start(self, package):
        self.stop()
        if ('KDE' not in os.environ.get('XDG_CURRENT_DESKTOP', '').split(':') or
                os.environ.get('XDG_SESSION_TYPE') != 'wayland'):
            return 'Fullscreen is managed by the current compositor.'
        try:
            self.qdbus = tool('qdbus6')
            self.name = 'apk-revival-game-' + uuid.uuid4().hex
            fd, filename = tempfile.mkstemp(prefix='apk-revival-fullscreen-', suffix='.js')
            self.script = pathlib.Path(filename)
            with os.fdopen(fd, 'w') as stream:
                stream.write(fullscreen_script(package))
            ident = command([self.qdbus, 'org.kde.KWin', '/Scripting',
                             'org.kde.kwin.Scripting.loadScript', filename, self.name], timeout=3).strip()
            if not ident.isdecimal():
                raise RevivalError('KDE did not accept the game fullscreen script.')
            command([self.qdbus, 'org.kde.KWin', '/Scripting/Script' + ident,
                     'org.kde.kwin.Script.run'], timeout=3)
            return 'Requested KDE fullscreen for ' + package + '.'
        except (RevivalError, OSError, ValueError) as error:
            self.stop()
            # Presentation failure must not prevent a working game from opening.
            return 'Game opened with desktop window controls: ' + str(error)

    def stop(self):
        if self.name and self.qdbus:
            try:
                command([self.qdbus, 'org.kde.KWin', '/Scripting',
                         'org.kde.kwin.Scripting.unloadScript', self.name], timeout=3)
            except RevivalError:
                pass
        self.name = None
        if self.script:
            self.script.unlink(missing_ok=True)
            self.script = None
