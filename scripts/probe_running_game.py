"""Read-only host probe of the current game. Never starts or stops a runtime."""
import json,os,pathlib,sys
from apk_revival.launcher.service import Launcher
from apk_revival.launcher.input_diagnostics import collect,LABELS
from apk_revival.store import Store
class Context:
    def step(self,message):print(message,flush=True)
launcher=Launcher(Store(pathlib.Path.home()/'.local/share/apk-revival'))
# Source probes may use a private interpreter. Host Waydroid must use its own
# Python, and passive diagnostics must not replace the application's state file.
os.environ.pop('PYTHONHOME',None)
os.environ.pop('PYTHONPATH',None)
launcher.runtime_manager.state_file=None
result=collect(launcher,LABELS[0],Context(),duration=5,settle=0)
# This passive sample must not be presented as a directed pinch trial.
report=result['report'];report['interaction']='Agent passive baseline; no physical gesture directed or observed.'
from apk_revival.util import atomic_json
atomic_json(pathlib.Path(result['directory'])/'report.json',report)
print(json.dumps({'directory':result['directory'],'focused_android_package':report.get('focused_android_package'),'errors':report['errors'],'surface_summaries':report.get('surface_summaries'),'input_snapshots':report.get('input_snapshots')},indent=2))
