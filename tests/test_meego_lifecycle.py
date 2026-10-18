"""Death/revival/age-20 contracts, plus real original native asset checks."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from apk_revival.meego.engine import lifecycle, local_game as g, simulation as sim, server
from apk_revival.meego import camera, ccb, lifecycle_mod
from apk_revival.util import RevivalError


def params(**values):
    return {k: [str(v).lower() if isinstance(v, bool) else str(v)] for k,v in values.items()}


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000000
        self.person = g.villager(1,'Favourite',1,[],7,self.now)
        self.person.update(birthday=self.now-80*3600,deathday=self.now+20*3600)
        self.person['stats'].update(strength=231,intelligence=184,charisma=97)
        self.person['items']={'5':{'item_id':5,'count':1}}
        self.person['job'].update(job_id=16,source_id=2,local_trip_seconds=4,local_fraction=.6)
        self.data={'format_version':1,'game_user':{'user_id':7},'last_simulated_at':self.now,
            'local_migrations':['starter-economy-1','completed-trips-2'],
            'skill_progress':{'1':{'strength':47}},
            'game_state':{'name':'local','all_villagers':{'1':self.person},
                'buildings':{'1':g.building(1,1,1,0,self.now)},
                'resources':{str(i):{'resource_id':i,'count':100,'last_update':self.now} for i in range(1,6)},
                'global_state':{},'items':{},'points':31,'achievements':{}}}
        self.rules={'buildings':{'1':{'size':2,'state_data':{'1':{'temple_level':1,'villager_slots':5,
            'resource_caps':{str(i):500 for i in range(1,6)}}}}},
            'jobs':{'0':{'type':0},'6':{'type':8},'16':{'type':3,'product_type':359}},
            'items':{},'points_store':{}}
        self.patch=patch.object(g,'RULES',self.rules);self.patch.start();self.addCleanup(self.patch.stop)

    def resolve(self,data=None,when=None,**fields):
        return sim.mutate(self.data if data is None else data,'game/village/confirm_dead_villager',
            params(villager_id=1,**fields),self.now if when is None else when)

    def assert_identity(self,before,after):
        for key in ('villager_id','name','gender','user_id','stats','appearance_items','items'):
            self.assertEqual(after[key],before[key],key)

    def test_living_elder_returns_to_twenty_and_keeps_stats_equipment_and_partial_work(self):
        before=copy.deepcopy(self.data)
        result=self.resolve(alive=True,use_points=False)
        person=result['game_state']['all_villagers']['1']
        self.assertEqual(sim.hours_age(person,self.now),20)
        self.assertEqual(person['deathday'],self.now+80*3600)
        self.assert_identity(self.person,person)
        self.assertEqual(person['job'],self.person['job'])
        self.assertEqual(result['skill_progress'],self.data['skill_progress'])
        self.assertEqual(result['game_state']['points'],31)
        self.assertEqual(self.data,before)

    def test_dead_meego_revives_once_at_twenty_with_fresh_model_and_clean_death_job(self):
        self.person['job']=g.idle_job(self.now-2);self.person['job']['job_id']=6
        self.person.update(last_update=self.now-2,deathday=self.now-2,local_offline_age_seconds=400)
        before=copy.deepcopy(self.person)
        result=self.resolve(alive=True,use_points=True)
        person=result['game_state']['all_villagers']['1']
        self.assertEqual(person['job']['job_id'],0)
        self.assertEqual(sim.hours_age(person,self.now),20)
        self.assertGreater(person['last_update'],before['last_update'])
        self.assert_identity(before,person)
        self.assertNotIn('local_offline_age_seconds',person)
        self.assertEqual(self.resolve(result,when=self.now+2,alive=True),result)
        restored=sim.advance(json.loads(json.dumps(result)),self.now+10)
        self.assertEqual(restored['game_state']['all_villagers']['1']['job']['job_id'],0)

    def test_native_clear_tombstone_deletes_instead_of_reviving_and_wire_removes_ghost(self):
        self.person['job']['job_id']=6
        result=self.resolve(alive=False,use_points=False)
        self.assertNotIn('1',result['game_state']['all_villagers'])
        wire=server.native_payload(result['game_state'],removed_villagers=result[lifecycle.REMOVED_KEY])
        self.assertIsNone(wire['all_villagers']['1'])
        self.assertEqual(self.resolve(result,alive=False),result)
        # Tombstone markers never erase a new villager reusing an old ID.
        result['game_state']['all_villagers']['1']=copy.deepcopy(self.person)
        self.assertIsNotNone(server.native_payload(result['game_state'],removed_villagers=result[lifecycle.REMOVED_KEY])['all_villagers']['1'])

    def test_living_meego_cannot_be_deleted_and_invalid_flags_are_rejected(self):
        for fields in ({'alive':False},{'alive':'yes'},{'use_points':'bad'}):
            before=copy.deepcopy(self.data)
            with self.assertRaises(g.ActionError):self.resolve(**fields)
            self.assertEqual(self.data,before)

    def test_children_foreign_and_away_villagers_are_preserved(self):
        for fields in ({'birthday':self.now-3*3600},{'user_id':999},{'location_type':1}):
            data=copy.deepcopy(self.data);data['game_state']['all_villagers']['1'].update(fields)
            before=copy.deepcopy(data)
            with self.assertRaises(g.ActionError):self.resolve(data,alive=True)
            self.assertEqual(data,before)

    def test_native_post_route_and_save_restart_keep_revival(self):
        self.person['job']['job_id']=6;self.person['deathday']=self.now-1
        self.person['last_update']=self.now-2
        seed=copy.deepcopy(self.data)
        with tempfile.TemporaryDirectory() as directory,patch.object(server.time,'time',return_value=self.now):
            server.atomic_json(Path(directory)/'saves/village.json',seed)
            state=server.State(directory,seed)
            value,status=state.handle('game/village/confirm_dead_villager',params(villager_id=1,alive=True,use_points=False))
            self.assertNotIn('exception',value)
            self.assertEqual(value['all_villagers']['1']['job']['job_id'],0)
            saved=copy.deepcopy(state.data)
            repeated,status=state.handle('game/village/confirm_dead_villager',params(villager_id=1,alive=True,use_points=False))
            self.assertNotIn('exception',repeated)
            restart=server.State(directory,seed)
            self.assertEqual(restart.data['game_state']['all_villagers']['1']['stats'],saved['game_state']['all_villagers']['1']['stats'])

    def test_removal_markers_never_apply_to_remote_or_adventure_views(self):
        for name in ('remote','dungeon'):
            state={'name':name,'buildings':{},'all_villagers':{}}
            self.assertEqual(server.native_payload(state,removed_villagers=('1',)),state)


@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'),'Requires privately owned original assets')
class NativeLifecycleAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive=zipfile.ZipFile(os.environ['APKR_MEEGO_APK'])
        cls.addClassCleanup(cls.archive.close)

    def panel(self,asset):
        raw=self.archive.read(asset)
        reader=ccb.Reader(raw);tree=reader.read()
        animations=sorted(n['animations'] for n in lifecycle_mod.walk(tree) if n['animations']!=b'\x01')
        self.assertEqual(reader.dump(tree),raw)
        result=lifecycle_mod.patched_panel(asset,raw)
        reader=ccb.Reader(result);tree=reader.read()
        self.assertEqual(reader.dump(tree),result)
        self.assertEqual(sorted(n['animations'] for n in lifecycle_mod.walk(tree) if n['animations']!=b'\x01'),animations)
        return tree

    def test_phone_and_tablet_stats_have_single_real_callback_below_age_icons(self):
        for asset in list(lifecycle_mod.ASSETS)[:2]:
            tree=self.panel(asset);nodes=list(lifecycle_mod.walk(tree))
            age=next(n for n in nodes if n['name']=='ageView')
            added=[n for n in lifecycle_mod.walk(age) if lifecycle_mod.props(n).get('block')==('onResurrect',2)]
            self.assertEqual(len(added),1)
            self.assertEqual(added[0]['assignment'],0)
            button=lifecycle_mod.props(added[0])
            self.assertEqual(button['position'],(400,62,0))
            self.assertTrue(any(lifecycle_mod.props(n).get('string')=='Return to age 20' for n in lifecycle_mod.walk(age)))
            self.assertTrue(any(lifecycle_mod.props(n).get('string')=='Keep all stats' for n in lifecycle_mod.walk(age)))
            self.assertEqual(len([n for n in nodes if n['name']=='buttonDeadResurrect']),1)

    def test_confirmation_offers_one_enabled_free_stat_preserving_action(self):
        tree=self.panel('assets/TombstonePopUp.ccbi')
        nodes=list(lifecycle_mod.walk(tree))
        callbacks=[lifecycle_mod.props(n) for n in nodes if 'block' in lifecycle_mod.props(n)]
        free=next(p for p in callbacks if p['block']==('onResurrectFree',2))
        paid=next(p for p in callbacks if p['block']==('onResurrect',2))
        self.assertEqual(free['isEnabled'],1)
        self.assertEqual(paid['visible'],0);self.assertEqual(paid['isEnabled'],0)
        strings=[lifecycle_mod.props(n).get('string') for n in nodes]
        self.assertIn('All stats kept',strings)
        self.assertNotIn('Partial Stat\n',strings)
        self.assertTrue(any(p['block']==('onClose',2) for p in callbacks))

    def test_unknown_or_modified_assets_fail_closed(self):
        for asset in lifecycle_mod.ASSETS:
            with self.assertRaises(RevivalError):lifecycle_mod.patched_panel(asset,self.archive.read(asset)+b'x')

    def test_signed_plan_contains_all_age_assets_and_requires_one_time_client_upgrade(self):
        from apk_revival.meego.adapter import MeegoAdapter,ORIGINAL_SHA
        from apk_revival.meego.plugin import MeegoPlugin
        store=Mock();store.base.return_value=Path(os.environ['APKR_MEEGO_APK'])
        profile=dict(adapter='meego-1.32',apk_sha256=ORIGINAL_SHA,apk_version={'name':'1.32','code':1},runtime={'backend_port':18765})
        plan=MeegoAdapter().plan(store,profile,'local_backend')
        operations=[o for o in plan['operations'] if o['type']=='meego_lifecycle_panel']
        self.assertEqual({o['file'] for o in operations},set(lifecycle_mod.ASSETS))
        plugin=MeegoPlugin()
        for operation in operations:
            plugin.validate_operation(operation,profile)
            modified,_=plugin.apply_operation(operation,self.archive.read(operation['file']))
            self.assertNotEqual(modified,self.archive.read(operation['file']))
        self.assertTrue(camera.prepared({'plan':plan}))
        old=copy.deepcopy(plan);del old['meego_client_fixes']['native_lifecycle_mod']
        self.assertFalse(camera.prepared({'plan':old}))
