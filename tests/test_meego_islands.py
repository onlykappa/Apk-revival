"""Offline Launch Dock protocol and persistence checks; never uses live saves."""
import copy
import json
import os
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from apk_revival.meego.engine import islands, local_game as g, server, simulation as sim, food


def params(**values):
    return {k: [str(v)] for k,v in values.items()}


class OfflineIslandTests(unittest.TestCase):
    def setUp(self):
        self.now=1_000_000
        self.rules={'items':{},'points_store':{},'jobs':{
            '0':{'type':0,'active':True},'7':{'type':4,'active':True},
            '8':{'type':9,'active':True}},'buildings':{
            '1':{'state_data':{'1':{'villager_slots':5,'temple_level':1,
                'resource_caps':{str(i):100 for i in range(1,6)}}}},
            '9':{'state_data':{'0':{'active_job':5},'1':{'active_job':7,'quest_villagers':4}}},
            **{str(i):{'state_data':{'1':{'active_job':15+i,'default_length':1}}} for i in (2,3,4)}}}
        self.rules_patch=patch.object(g,'RULES',self.rules);self.rules_patch.start()
        self.addCleanup(self.rules_patch.stop)
        self.seed=json.loads((Path(__file__).resolve().parents[1]/'resources/meego-starter.json').read_text())
        self.data=server.initial_village(self.seed,self.now,self.rules)
        self.data['game_state']['buildings']['9']=g.building(9,9,1,200,self.now)
        self.dest=islands.ISLANDS[0][0]

    def depart(self,data=None,pid=1,dest=None,duration=60):
        return islands.send(self.data if data is None else data,
            params(villager_id=pid,to_user_id=dest or self.dest,duration=duration),self.rules,self.now)

    def collect(self,data,ids=(1,),now=None):
        return islands.collect(data,params(reward_villager_ids=json.dumps(list(ids))),
                               self.rules,self.now+60 if now is None else now)

    def test_exactly_three_stable_local_neighbours_and_bounded_size(self):
        before=copy.deepcopy(self.data)
        _,rows=islands.handle(self.data,'game/village/get_neighbour_list',params(size=40),self.rules,self.seed,self.now)
        self.assertEqual([r['user_id'] for r in rows],[r[0] for r in islands.ISLANDS])
        self.assertEqual(len({r['username'] for r in rows}),3)
        self.assertTrue(all('(Local)' in r['username'] and not r['facebook_id'] for r in rows))
        _,empty=islands.handle(self.data,'game/village/get_neighbour_list',params(size=0),self.rules,self.seed,self.now)
        self.assertEqual(empty,[])
        self.assertEqual(self.data,before)

    def test_remote_snapshots_are_isolated_and_each_has_its_specialty(self):
        before=copy.deepcopy(self.data)
        for ident,name,resource,kind in islands.ISLANDS:
            packet=islands.remote(self.data,ident,self.seed,self.rules,self.now)
            self.assertEqual(set(packet),{'profile','game_state'})
            self.assertEqual(packet['game_state']['name'],'remote')
            self.assertEqual(packet['profile']['username'],name)
            self.assertEqual(sum(b['building_type']==kind for b in packet['game_state']['buildings'].values()),3)
            self.assertTrue(all(p['user_id']==ident for p in packet['game_state']['all_villagers'].values()))
            packet['game_state']['resources']['1']['count']=99999
        self.assertEqual(self.data,before)

    def test_depart_retry_preserves_deadline_inventory_stats_and_home_housing(self):
        person=self.data['game_state']['all_villagers']['1']
        person['items']={'371':{'item_id':371,'count':1}}
        person['stats']['strength']=25
        before=copy.deepcopy(self.data)
        new=self.depart()
        traveller=new['game_state']['all_villagers']['1']
        self.assertFalse(g.at_home(traveller))
        self.assertEqual(traveller['location_type'],0)
        self.assertEqual(traveller['location_id'],self.dest)
        self.assertEqual(traveller['items'],person['items'])
        self.assertEqual(traveller['stats'],person['stats'])
        self.assertEqual(self.depart(new),new)
        self.assertEqual(len(new['game_state']['all_villagers']),2)
        self.assertEqual(food.consumption_rate(new),1)
        self.assertEqual(self.data,before)
        remote=islands.remote(new,self.dest,self.seed,self.rules,self.now)
        self.assertIn('1',remote['game_state']['all_villagers'])
        self.assertEqual(remote['profile']['guest_count'],1)

    def test_early_reward_is_rejected_without_any_mutation(self):
        new=self.depart();before=copy.deepcopy(new)
        with self.assertRaises(g.ActionError):self.collect(new,now=self.now+59)
        self.assertEqual(new,before)

    def test_return_and_reward_survive_json_restart_and_retry_without_duplicate_credit(self):
        new=json.loads(json.dumps(self.depart()))
        islands.advance(new,self.now+60)
        p=new['game_state']['all_villagers']['1']
        self.assertTrue(g.at_home(p));self.assertEqual(p['job']['job_id'],8)
        self.assertEqual(new['game_state']['resources']['1']['count'],0)
        settled,response=self.collect(new)
        self.assertEqual(set(response),{'game_state','quest_results'})
        self.assertEqual(response['quest_results']['1']['resource_rewards'],{'1':5})
        self.assertEqual(settled['game_state']['resources']['1']['count'],5)
        self.assertEqual(settled['game_state']['all_villagers']['1']['stats']['charisma'],11)
        self.assertEqual(settled['game_state']['all_villagers']['1']['job']['job_id'],0)
        retry,reply=self.collect(json.loads(json.dumps(settled)))
        self.assertEqual(retry,settled);self.assertEqual(reply,response)

    def test_all_three_resource_rewards_use_real_bank_and_capacity(self):
        for ident,_,resource,_ in islands.ISLANDS:
            new=self.depart(dest=ident)
            new['game_state']['resources'][str(resource)]['count']=98
            settled,response=self.collect(new)
            self.assertEqual(settled['game_state']['resources'][str(resource)]['count'],100)
            self.assertEqual(response['quest_results']['1']['resource_rewards'],{str(resource):2})

    def test_duplicate_and_forged_reward_ids_are_atomic(self):
        new=self.depart();before=copy.deepcopy(new)
        for ids in ((1,1),(1,999),(999,)):
            with self.subTest(ids=ids),self.assertRaises(g.ActionError):self.collect(new,ids)
            self.assertEqual(new,before)

    def test_depart_rejects_unknown_islands_and_unbounded_or_too_short_duration(self):
        before=copy.deepcopy(self.data)
        for dest,duration in ((999,60),(self.dest,0),(self.dest,59),(self.dest,86401)):
            with self.subTest(dest=dest,duration=duration),self.assertRaises(g.ActionError):
                self.depart(dest=dest,duration=duration)
        self.assertEqual(self.data,before)

    def test_baby_dead_foreign_busy_and_away_villagers_cannot_depart(self):
        for change in ({'birthday':self.now-3600},{'deathday':self.now-1},
                       {'user_id':99},{'location_id':99},{'location_type':1},
                       {'job':{'job_id':3}}):
            data=copy.deepcopy(self.data);data['game_state']['all_villagers']['1'].update(change)
            before=copy.deepcopy(data)
            with self.subTest(change=change),self.assertRaises(g.ActionError):self.depart(data)
            self.assertEqual(data,before)

    def test_no_completed_dock_no_departure(self):
        self.data['game_state']['buildings']['9']['state']=0
        with self.assertRaises(g.ActionError):self.depart()

    def test_three_guest_limit_and_completed_home_dock_capacity(self):
        for pid in range(3,6):
            self.data['game_state']['all_villagers'][str(pid)]=g.villager(pid,'Fixture',1,[],1,self.now)
        data=self.data
        for pid in (1,2,3):data=self.depart(data,pid=pid)
        with self.assertRaisesRegex(g.ActionError,'three visitors'):self.depart(data,pid=4)
        data=self.depart(data,pid=4,dest=islands.ISLANDS[1][0])
        with self.assertRaisesRegex(g.ActionError,'Dock is full'):self.depart(data,pid=5,dest=islands.ISLANDS[2][0])

    def test_home_worker_assignment_and_breeding_reject_away_villager(self):
        data=self.depart()
        with self.assertRaises(g.ActionError):sim.mutate(data,'game/village/set_job',params(villager_id=1,job_id=0),self.now+1)
        with self.assertRaises(g.ActionError):sim.compatible(data['game_state'],*data['game_state']['all_villagers'].values(),self.now)

    def test_simulation_returns_traveller_after_long_offline_time_without_harvest(self):
        data=self.depart()
        result=sim.advance(json.loads(json.dumps(data)),self.now+3600,food_active=False)
        self.assertEqual(result[islands.KEY]['trips']['1']['status'],'ready')
        self.assertTrue(g.at_home(result['game_state']['all_villagers']['1']))
        self.assertEqual(result['game_state']['resources']['1']['count'],0)
        self.assertEqual(result['game_state']['all_villagers']['1']['items'],data['game_state']['all_villagers']['1']['items'])

    def test_second_trip_earns_one_new_reward_and_does_not_grow_history_per_trip(self):
        settled,_=self.collect(self.depart())
        again=islands.send(settled,params(villager_id=1,to_user_id=self.dest,duration=60),self.rules,self.now+61)
        self.assertEqual(again[islands.KEY]['trips']['1']['id'],2)
        final,_=self.collect(again,now=self.now+121)
        self.assertEqual(final['game_state']['resources']['1']['count'],10)
        self.assertEqual(len(final[islands.KEY]['trips']),1)

    def test_late_return_and_collection_cannot_resurrect_dead_villager(self):
        data=self.depart();data['game_state']['all_villagers']['1']['deathday']=self.now+70
        result=sim.advance(data,self.now+100,food_active=False)
        collected,_=self.collect(result,now=self.now+100)
        self.assertEqual(collected['game_state']['all_villagers']['1']['job']['job_id'],6)

    def test_moving_dock_updates_active_trip_and_return_source(self):
        from apk_revival.meego.engine import relocation
        data=self.depart()
        relocation.move(data,'9',300,0,self.now+1)
        self.assertEqual(data[islands.KEY]['trips']['1']['dock_id'],300)
        islands.advance(data,self.now+60)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['source_id'],300)
        collected,_=self.collect(data)
        self.assertEqual(collected['game_state']['resources']['1']['count'],5)

    def test_pending_reward_cannot_be_discarded_by_job_assignment(self):
        data=self.depart();islands.advance(data,self.now+60)
        with self.assertRaisesRegex(g.ActionError,'Collect'):
            sim.mutate(data,'game/village/set_job',params(villager_id=1,job_id=0),self.now+61)

    def test_destination_change_and_pending_depart_retry_cannot_reset_trip(self):
        data=self.depart();before=copy.deepcopy(data)
        with self.assertRaises(g.ActionError):self.depart(data,dest=islands.ISLANDS[1][0])
        self.assertEqual(data,before)
        islands.advance(data,self.now+60)
        self.assertEqual(self.depart(data),data)

    def test_server_routes_persist_and_remote_view_does_not_replace_home(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(server.time,'time',return_value=self.now):
            server.atomic_json(Path(directory)/'saves/village.json',self.data)
            state=server.State(directory,self.seed)
            before=copy.deepcopy(state.data['game_state'])
            rows,status=state.handle('game/village/get_neighbour_list',params(size=40))
            self.assertEqual(len(rows),3)
            packet,status=state.handle('game/village/get_remote_village',params(village_id=self.dest))
            self.assertEqual(packet['game_state']['name'],'remote')
            self.assertEqual(state.data['game_state'],before)
            wrong,_=state.handle('game/village/get_village',params(village_id=999))
            self.assertIn('exception',wrong)
            state.handle('game/village/send_villager',params(villager_id=1,to_user_id=self.dest,duration=60))
            self.assertFalse(g.at_home(state.data['game_state']['all_villagers']['1']))
            with patch.object(server.time,'time',return_value=self.now+60):
                resumed=server.State(directory,self.seed)
                reply,status=resumed.handle('game/village/update_villager_quest',params(villager_id=1))
                self.assertEqual(reply['all_villagers']['1']['job']['job_id'],8)
                result,status=resumed.handle('game/village/complete_quest',params(reward_villager_ids='[1]'))
                self.assertEqual(result['quest_results']['1']['resource_rewards'],{'1':5})
                repeated,_=resumed.handle('game/village/complete_quest',params(reward_villager_ids='[1]'))
                self.assertEqual(repeated['game_state']['resources']['1']['count'],5)
                home,_=resumed.handle('game/village/get_village',params(village_id=1))
                self.assertEqual(home['name'],'local' if before['name']=='local' else before['name'])


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'),'Requires privately owned original APK')
class OriginalIslandContractTests(unittest.TestCase):
    def setUp(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            self.rules=plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        self.seed=json.loads((Path(__file__).resolve().parents[1]/'resources/meego-starter.json').read_text())
        self.rule_patch=patch.object(g,'RULES',self.rules);self.rule_patch.start()
        self.addCleanup(self.rule_patch.stop)
        self.now=1_000_000
        self.data=server.initial_village(self.seed,self.now,self.rules)
        self.data['game_state']['buildings']['9']=g.building(9,9,1,2000,self.now)

    def test_native_two_hour_trip_wait_return_collect_using_original_dock_jobs(self):
        data=sim.mutate(self.data,'game/village/set_job',
            params(villager_id=1,job_id=7,job_data=json.dumps({'source_id':9})),self.now)
        data=islands.send(data,params(villager_id=1,to_user_id=islands.ISLANDS[0][0],duration=7200),self.rules,self.now)
        wire=server.native_payload(data['game_state'])
        self.assertEqual(wire['all_villagers']['1']['quest']['end_date'],float(self.now+7200))
        early=sim.advance(data,self.now+7199,food_active=False)
        self.assertFalse(g.at_home(early['game_state']['all_villagers']['1']))
        result=sim.advance(json.loads(json.dumps(early)),self.now+7200,food_active=False)
        self.assertEqual(result['game_state']['all_villagers']['1']['job']['job_id'],8)
        collected,response=islands.collect(result,params(reward_villager_ids='[1]'),self.rules,self.now+7200)
        self.assertEqual(collected['game_state']['resources']['1']['count'],100)
        self.assertEqual(response['quest_results']['1']['resource_rewards'],{'1':100})
        retry,_=islands.collect(collected,params(reward_villager_ids='[1]'),self.rules,self.now+7201)
        self.assertEqual(retry['game_state']['resources']['1']['count'],100)

    def test_remote_original_footprints_are_valid_and_do_not_overlap(self):
        for island in islands.ISLANDS:
            gs=islands.remote(self.data,island[0],self.seed,self.rules,self.now)['game_state']
            for key,node in gs['buildings'].items():
                g.check_placement(gs,node['building_type'],node['location'],ignore=key)
            wire=server.native_payload(gs)
            self.assertEqual(wire['name'],'remote')
            self.assertEqual(len(wire['all_villagers']),2)


if __name__=='__main__':unittest.main()
