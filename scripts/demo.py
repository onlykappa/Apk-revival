#!/usr/bin/env python3
"""Real APK build/export demo; host protocol checks are not Android gameplay proof."""
import argparse, pathlib, sys, urllib.request, json, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apk_revival.store import Store
from apk_revival.analysis import analyze
from apk_revival.restoration import Restorer
from apk_revival.exporter import export_game
from apk_revival.backend import Backend
from apk_revival.saves import Saves
from apk_revival.util import atomic_json, digest

p=argparse.ArgumentParser();p.add_argument('--apk',default=str(ROOT/'build/tapquest-original.apk'));p.add_argument('--data',default=str(ROOT/'build/demo-data'));p.add_argument('--out',default=str(ROOT/'build/demo-exports'));a=p.parse_args()
s=Store(a.data);original=digest(a.apk);profile=s.import_game(a.apk);game=profile['id'];report=analyze(s,game);restorer=Restorer(s);outputs=[]
for path in ['offline_patch','local_backend','rebuild']:
    restorer.plan(game,path);prepared=restorer.prepare(game,path)
    if path=='local_backend':
        save=s.directory(game)/'saves/tapquest.json'
        with Backend(save,port=0) as backend:
            base='http://127.0.0.1:'+str(backend.port)
            initial=json.load(urllib.request.urlopen(base+'/state'))
            request=urllib.request.Request(base+'/action',data=b'{"action":"collect"}',headers={'Content-Type':'application/json'})
            action=json.load(urllib.request.urlopen(request))
            assert action['coins']==initial['coins']+1
        with Backend(save,port=0) as backend:
            reloaded=json.load(urllib.request.urlopen('http://127.0.0.1:'+str(backend.port)+'/state'));assert reloaded==action
        backup=Saves(s).backup(game);Saves(s).restore(game,backup)
    outputs.append(export_game(s,game,pathlib.Path(a.out)/(path+'.zip')))
    assert digest(a.apk)==original
summary={'fixture':'self-authored executable Android APK','original_sha256':original,'game_id':game,'exports':outputs,'tested':['Real binary APK import and AXML/DEX inspection','Reviewed config patch, rebuild, alignment and signature verification','Host local backend progression, restart persistence and save backup/restore','Independent fixture rebuild packaging','Export hashes and private-file exclusions'],'unverified':['Android cold launch and meaningful gameplay','Android-to-host backend reachability','Guest egress enforcement','Android save/relaunch and backend failure recovery','Desktop rebuild interaction on Android is not applicable'],'status':'Exported but Unverified'}
atomic_json(pathlib.Path(a.out)/'demo-result.json',summary);print(json.dumps(summary,indent=2))
