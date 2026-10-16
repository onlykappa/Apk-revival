"""Developer-only runtime probe. Run normally, never through REA process capture.

Process capture owns/cleans descendants and can close the compositor started here.
Use the normal APK Revival Play interface for real-device launch verification.
"""
import json
from apk_revival.launcher.runtime_setup import RuntimeManager
from apk_revival.launcher.tools_setup import configure
configure()
manager=RuntimeManager()
def progress(message):print(message,flush=True)
try:
    serial=manager.ensure(progress=progress)
    print(json.dumps({'ready':True,'serial':serial,'runtime':manager.last},indent=2),flush=True)
except Exception as error:
    print(json.dumps({'ready':False,'error':str(error)},indent=2),flush=True)
    raise
