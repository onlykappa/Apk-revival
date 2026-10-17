"""Trusted adapters generate reviewable data plans. Imported profiles are not code."""
from __future__ import annotations
import hashlib, json, zipfile
from .util import RevivalError

PATHS=('offline_patch','local_backend','rebuild')

class TapQuestAdapter:
    name='tapquest-v1';supported_paths=PATHS
    def feasibility(self,p):
        return {'feasible':True,'classification':'self-authored fixture','mechanics':['Collect one coin per tap','Level increases every 10 coins','Persistent progress'],'recoverable_assets':['No proprietary assets; interface drawn with text/buttons'],'needs_implementation':['Independent desktop user interface'],'limitations':['Does not demonstrate recovery of any commercial game'],'implemented':True}
    def plan(self,store,p,path):
        if path not in PATHS:raise RevivalError('Unknown path')
        plan={'schema_version':1,'adapter':self.name,'apk_sha256':p['apk_sha256'],'apk_version':p['apk_version'],'path':path,'operations':[],'assumptions':[],'backend':None,'save_locations':[]}
        if path=='rebuild':plan['feasibility']=self.feasibility(p);return plan
        with zipfile.ZipFile(store.base(p)) as z:raw=z.read('assets/revival.json')
        config=json.loads(raw)
        if config.get('fixture')!='tapquest-v1':raise RevivalError('Fixture config mismatch')
        config['mode']='offline' if path=='offline_patch' else 'remote'
        config['endpoint']=f'http://127.0.0.1:{p["runtime"]["backend_port"]}' if path=='local_backend' else ''
        plan['operations']=[{'type':'replace_text_file','file':'assets/revival.json','expected_sha256':hashlib.sha256(raw).hexdigest(),'content':json.dumps(config,indent=2)+'\n','reason':'Select the existing local gameplay branch.' if path=='offline_patch' else 'Route documented fixture protocol through verified ADB reverse forwarding.'}]
        plan['save_locations']=['SharedPreferences: tapquest.xml'] if path=='offline_patch' else ['host saves/tapquest.json']
        if path=='local_backend':plan['backend']={'protocol':'tapquest-v1','evidence':'fixtures/android/src/org/apkrevival/tapquest/MainActivity.java and docs/FIXTURE.md','endpoints':['GET /health','GET /state','POST /action {action:collect}'],'assumptions':['Single-player local progression only. No accounts, purchases or multiplayer.']}
        return plan

ADAPTERS={'tapquest-v1':TapQuestAdapter()}

def register(instance):
    """Called by game plugins to add their adapter."""
    ADAPTERS[instance.name]=instance

def load_plugins(*folders):
    from . import plugins
    return plugins.load(register,folders)

load_plugins()

def find(p):
    """The registered adapter for a profile, or None."""
    return ADAPTERS.get(p.get('adapter')) if p and p.get('adapter') else None

def missing_plugin(p):
    """Name of the plugin a game needs but which is not installed, else None."""
    name=p.get('adapter') if p else None
    from .plugins import plugin_for
    return plugin_for(name) if name and name not in ADAPTERS else None

def adapter(p):
    if missing_plugin(p):raise RevivalError('This game needs the '+missing_plugin(p)+' game plugin. Install it from Setup > Game plugins. Your game files and saves are kept.')
    if not p.get('adapter') or p['adapter'] not in ADAPTERS:raise RevivalError('Needs Evidence: no trusted game adapter. Use analysis report and develop a reviewed adapter; V1 cannot convert this game automatically.')
    return ADAPTERS[p['adapter']]

