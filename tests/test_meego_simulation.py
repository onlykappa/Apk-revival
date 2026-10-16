"""Private-file simulation parity checks; fixed clocks are explicit test inputs."""
import copy,io,json,os,pathlib,plistlib,tempfile,unittest,zipfile
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import patch
from apk_revival.store import Store
from apk_revival.launcher.service import Launcher
from apk_revival.util import atomic_json,digest
from test_pipeline import make_apk
from apk_revival.meego.engine import server,simulation as sim,local_game as g

def params(**values):return {k:[str(v)] for k,v in values.items()}

@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'),'Requires privately owned bundled Meego rules')
class MeegoSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as z:tree=plistlib.loads(z.read('assets/TechTree.plist'))['techtree']
        g.RULES={k:tree[k] for k in ['buildings','items','jobs','points_store']}
        seed=json.loads((pathlib.Path(__file__).resolve().parents[1]/'resources/meego-starter.json').read_text());self.state=server.State(self.temp.name,seed)
        # Economy tests explicitly fund only their temporary village; new real
        # villages now start without the former test supplies and skulls.
        funded=copy.deepcopy(self.state.data)
        funded['game_state']['resources']=copy.deepcopy(seed['game_state']['resources'])
        funded['game_state']['points']=25;self.state.persist(funded)
        self.data=copy.deepcopy(self.state.data);self.now=self.data['last_simulated_at']
    def tearDown(self):self.temp.cleanup()
    def dispatch(self,route,**values):
        # Exercise the real request parser, action simulation, recording and
        # response selection with an in-memory HTTP boundary (no TCP required).
        class Capture(server.Handler):
            def __init__(inner):
                inner.client_address=('127.0.0.1',12345)
                inner.path='/'+route+'/?'+urlencode(values)
                inner.headers={};inner.rfile=io.BytesIO()
                inner.server=SimpleNamespace(state=self.state)
            def reply(inner,code,value):inner.result=(code,server.native_payload(value))
        handler=Capture()
        with patch('apk_revival.meego.engine.server.time.time',return_value=self.now):handler.dispatch()
        return handler.result
    def test_real_pairing_rejection_uses_failure_callback_and_keeps_villagers(self):
        d=copy.deepcopy(self.state.data)
        for ident in range(3,6):
            person=copy.deepcopy(d['game_state']['all_villagers']['1']);person['villager_id']=ident
            d['game_state']['all_villagers'][str(ident)]=person
        self.state.persist(d)
        before=copy.deepcopy(self.state.data['game_state']['all_villagers'])
        for route in ('check_breeding_compatibility','breed'):
            code,value=self.dispatch('game/village/'+route,father_id=1,mother_id=2)
            self.assertEqual(code,409)
            self.assertIsInstance(value['exception'],str)
            self.assertIn('hut',json.loads(value['exception'])['message'])
            self.assertNotIn('token',value)
        self.assertEqual(self.state.data['game_state']['all_villagers'],before)
        log=json.loads(self.state.logfile.read_text().splitlines()[-1])
        self.assertIn('hut',log['error']['message'])
        self.assertIn('hut',self.state.take_action_notice())
        self.assertIsNone(self.state.take_action_notice())
    def test_starter_temple_allows_pairing_without_extra_huts(self):
        self.assertEqual(sim.housing(self.state.data['game_state']),5)
        code,value=self.dispatch('game/village/check_breeding_compatibility',father_id=1,mother_id=2)
        self.assertEqual(code,200)
        code,value=self.dispatch('game/village/breed',father_id=1,mother_id=2,token=value['token'])
        self.assertEqual(code,200);self.assertEqual(len(value['all_villagers']),3)
    def test_fresh_village_has_no_bonuses_and_restart_does_not_refill(self):
        state=server.State(pathlib.Path(self.temp.name)/'fresh',self.state.seed)
        self.assertEqual(len(state.data['game_state']['all_villagers']),2)
        self.assertTrue(all(r['count']==0 for r in state.data['game_state']['resources'].values()))
        self.assertEqual(state.data['game_state']['points'],0)
        self.assertFalse(state.data['start_profile']['original_server_defaults_verified'])
        self.assertEqual(server.State(state.directory,self.state.seed).data,state.data)
    def test_launcher_fresh_start_backs_up_old_village_and_preserves_apk(self):
        store=Store(pathlib.Path(self.temp.name)/'launcher')
        profile=store.import_game(make_apk(pathlib.Path(self.temp.name)/'test.apk'))
        profile['adapter']='meego-1.32';directory=store.directory(profile['id'])
        config=directory/'private-config';config.mkdir()
        atomic_json(config/'starter-packet.json',self.state.seed)
        atomic_json(config/'local-rules.json',g.RULES)
        profile['restoration'].update(path='local_backend',backend_data={'directory':'private-config','files':{p.name:digest(p) for p in config.iterdir()}})
        store.save(profile);atomic_json(directory/'saves/village.json',self.state.data)
        before=copy.deepcopy(self.state.data);apk_hash=digest(store.base(profile))
        launcher=Launcher(store)
        result=launcher.jobs.run('New village',lambda ctx:launcher.new_meego_village(profile['id'],ctx))
        with zipfile.ZipFile(result['previous_backup']) as z:self.assertEqual(json.loads(z.read('progress.json')),before)
        fresh=json.loads((directory/'saves/village.json').read_text())
        self.assertEqual(fresh['game_state']['points'],0)
        self.assertEqual(len(fresh['game_state']['all_villagers']),2)
        self.assertEqual(digest(store.base(profile)),apk_hash)
    def test_upgrading_buildings_keep_current_rule_capacity(self):
        gs=copy.deepcopy(self.state.data['game_state'])
        gs['buildings']['2']=g.building(2,5,10,676,self.now)
        self.assertEqual(sim.housing(gs),6)
    def test_hut_completion_polls_and_movement_keep_completed_state(self):
        code,value=self.dispatch('game/village/place_building',building_type_id=5,location=676,orientation=1)
        self.assertEqual(code,200)
        hut=next(b for b in value['buildings'].values() if b['building_type']==5)
        ident=hut['building_id']
        self.assertEqual(hut['state'],0)
        self.assertEqual(self.dispatch('game/village/set_job',villager_id=1,job_id=5,job_data=json.dumps({'source_id':ident}))[0],200)
        self.now+=10
        for _ in range(4):
            code,value=self.dispatch('game/village/update_building',building_type_id=5,building_id=ident)
            self.assertEqual(code,200)
            hut=value['buildings'][str(ident)]
            self.assertEqual((hut['state'],hut['progress']),(1,0))
            self.assertNotIn('expire_date',hut)
            self.assertEqual(self.state.data['game_state']['buildings'][str(ident)]['expire_date'],0)
            self.assertEqual(value['all_villagers']['1']['job']['job_id'],0)
            self.now+=1
        code,value=self.dispatch('game/village/move_building',building_id=ident,to_position=750,orientation=0)
        self.assertEqual(code,200);self.assertEqual(value['buildings'][str(ident)]['state'],1)
        self.assertEqual(sim.housing(value),6)
        saved=server.State(self.temp.name,self.state.seed).data
        self.assertEqual(saved['game_state']['buildings'][str(ident)]['state'],1)
    def test_successful_native_pairing_has_token_and_creates_one_baby(self):
        d=copy.deepcopy(self.state.data)
        d['game_state']['buildings']['2']=g.building(2,5,21,676,self.now)
        self.state.persist(d)
        code,value=self.dispatch('game/village/check_breeding_compatibility',father_id=1,mother_id=2)
        self.assertEqual(code,200);token=value['token'];self.assertIn('game_state',value)
        code,value=self.dispatch('game/village/breed',father_id=1,mother_id=2,token=token)
        self.assertEqual(code,200);self.assertEqual(len(value['all_villagers']),3)
        self.assertEqual(self.dispatch('game/village/breed',father_id=1,mother_id=2,token=token),(code,value))
        self.assertEqual(server.State(self.temp.name,self.state.seed).data,self.state.data)
    def test_missing_or_invalid_token_never_creates_a_baby(self):
        d=copy.deepcopy(self.state.data)
        d['game_state']['buildings']['2']=g.building(2,5,21,676,self.now)
        self.state.persist(d)
        for token in ('','wrong'):
            code,value=self.dispatch('game/village/breed',father_id=1,mother_id=2,token=token)
            self.assertEqual(code,409);self.assertIn('expired',json.loads(value['exception'])['message'])
            self.assertEqual(len(self.state.data['game_state']['all_villagers']),2)
    def test_unsupported_action_returns_failure_and_does_not_change_save(self):
        before=copy.deepcopy(self.state.data)
        code,value=self.dispatch('game/village/not_implemented')
        self.assertEqual(code,501);self.assertIn('exception',value)
        self.assertEqual(self.state.data,before)
    def test_gathering_caps_depletion_construction_and_restart(self):
        d=sim.mutate(self.data,'game/village/place_resource',params(building_type_id=3,location=3845),self.now);tree=next(b for b in d['game_state']['buildings'].values() if b['building_type']==3);d['game_state']['resources']['2']['count']=100
        d=sim.mutate(d,'game/village/set_job',params(villager_id=1,job_id=17,job_data=json.dumps({'source_id':tree['building_id'],'destination_id':1})),self.now);d=sim.advance(d,self.now+20);self.assertEqual(d['game_state']['resources']['2']['count'],102);self.assertEqual(d['game_state']['buildings'][str(tree['building_id'])]['count'],28);self.assertEqual(sim.advance(d,self.now+20),d)
        capped=copy.deepcopy(d);capped['game_state']['resources']['2']['count']=499;capped=sim.advance(capped,self.now+40);self.assertEqual(capped['game_state']['resources']['2']['count'],500)
        depleted=copy.deepcopy(d);depleted['game_state']['buildings'][str(tree['building_id'])]['count']=1;depleted=sim.advance(depleted,self.now+40);self.assertNotIn(str(tree['building_id']),depleted['game_state']['buildings'])
        d=sim.mutate(d,'game/village/place_building',params(building_type_id=5,location=676,orientation=1),self.now+20);hut=next(b for b in d['game_state']['buildings'].values() if b['building_type']==5);self.assertEqual(hut['state'],0);d=sim.mutate(d,'game/village/set_job',params(villager_id=2,job_id=5,job_data=json.dumps({'source_id':hut['building_id']})),self.now+20);d=sim.advance(d,self.now+80);self.assertEqual(d['game_state']['buildings'][str(hut['building_id'])]['state'],1);self.assertEqual(d['game_state']['all_villagers']['2']['job']['job_id'],0)
        self.state.persist(d);self.assertEqual(server.State(self.temp.name,self.state.seed).data,d)
    def test_breeding_is_idempotent_and_aging_is_bounded(self):
        d=sim.mutate(self.data,'game/village/place_building',params(building_type_id=5,location=676,orientation=1),self.now);hut=next(b for b in d['game_state']['buildings'].values() if b['building_type']==5);d['game_state']['buildings'][str(hut['building_id'])]['state']=21
        d=sim.mutate(d,'game/village/check_breeding_compatibility',params(father_id=1,mother_id=2),self.now);token=d['response_token'];d=sim.mutate(d,'game/village/breed',params(father_id=1,mother_id=2,token=token),self.now);self.assertEqual(len(d['game_state']['all_villagers']),3);self.assertEqual(sim.mutate(d,'game/village/breed',params(father_id=1,mother_id=2,token=token),self.now),d)
        d=sim.advance(d,self.now+7201);self.assertEqual(d['game_state']['all_villagers']['3']['job']['job_id'],2);d=sim.advance(d,self.now+36001);self.assertEqual(d['game_state']['all_villagers']['3']['job']['job_id'],0)
        with self.assertRaises(g.ActionError):sim.mutate(d,'game/village/set_job',params(villager_id=1,job_id=999),self.now+36001)

    def test_harvest_requires_completed_trip_and_partial_trip_survives_restart(self):
        d=sim.mutate(self.data,'game/village/place_resource',params(building_type_id=3,location=3845),self.now)
        tree=next(b for b in d['game_state']['buildings'].values() if b['building_type']==3)
        d['game_state']['resources']['2']['count']=0
        d=sim.mutate(d,'game/village/set_job',params(villager_id=1,job_id=17,job_data=json.dumps({'source_id':tree['building_id'],'destination_id':1})),self.now)
        d=sim.advance(d,self.now+11)
        self.assertEqual(d['game_state']['resources']['2']['count'],0)
        restored=json.loads(json.dumps(d));restored=sim.advance(restored,self.now+12)
        self.assertEqual(restored['game_state']['resources']['2']['count'],2)
        self.assertEqual(restored['game_state']['buildings'][str(tree['building_id'])]['count'],28)
        self.assertEqual(sim.advance(restored,self.now+12),restored)

    def test_old_node_migration_preserves_balances_and_repeated_load(self):
        d=copy.deepcopy(self.data);d['local_migrations'].remove('completed-trips-2')
        for i,kind in enumerate((2,3,4),2):
            d['game_state']['buildings'][str(i)]=g.building(i,kind,1,3000+i*100,self.now)
            d['game_state']['buildings'][str(i)]['count']=500
        balances=copy.deepcopy(d['game_state']['resources'])
        self.state.persist(d);loaded=server.State(self.temp.name,self.state.seed)
        self.assertEqual([loaded.data['game_state']['buildings'][str(i)]['count'] for i in (2,3,4)],[40,30,75])
        self.assertEqual(loaded.data['game_state']['resources'],balances)
        self.assertEqual(server.State(self.temp.name,self.state.seed).data,loaded.data)

    def test_depletion_releases_all_workers_and_full_storage_does_not_grant_stats(self):
        d=sim.mutate(self.data,'game/village/place_resource',params(building_type_id=3,location=3845),self.now)
        tree=next(b for b in d['game_state']['buildings'].values() if b['building_type']==3)
        d['game_state']['resources']['2']['count']=0;tree['count']=1
        for ident in (1,2):
            d=sim.mutate(d,'game/village/set_job',params(villager_id=ident,job_id=17,job_data=json.dumps({'source_id':tree['building_id'],'destination_id':1})),self.now)
        d=sim.advance(d,self.now+12)
        self.assertNotIn(str(tree['building_id']),d['game_state']['buildings'])
        self.assertTrue(all(p['job']['job_id']==0 for p in d['game_state']['all_villagers'].values()))
        self.assertEqual(d['game_state']['resources']['2']['count'],1)
        d=sim.mutate(d,'game/village/place_resource',params(building_type_id=3,location=3845),self.now+12)
        tree=next(b for b in d['game_state']['buildings'].values() if b['building_type']==3)
        d=sim.mutate(d,'game/village/set_job',params(villager_id=1,job_id=17,job_data=json.dumps({'source_id':tree['building_id'],'destination_id':1})),self.now+12)
        d['game_state']['resources']['2']['count']=500
        old=copy.deepcopy(d.get('skill_progress',{}));d=sim.advance(d,self.now+132)
        self.assertEqual(d.get('skill_progress',{}),old)

    def test_consumable_and_school_native_response_shapes(self):
        d=copy.deepcopy(self.state.data);d['game_state']['items']['830']={'item_id':830,'count':1,'last_update':self.now}
        self.state.persist(d)
        code,value=self.dispatch('game/village/use_villager_item',villager_id=1,item_id=830)
        self.assertEqual(code,200);self.assertIn('all_villagers',value)
        self.assertEqual(value['items']['830']['count'],0)
        d=copy.deepcopy(self.state.data);d['game_state']['buildings']['10']=g.building(10,30,1,3200,self.now)
        d['game_state']['all_villagers']['2']['birthday']=self.now-3*3600
        d['game_state']['all_villagers']['2']['job']['job_id']=2;self.state.persist(d)
        code,value=self.dispatch('game/village/set_job',villager_id=1,job_id=46,job_data=json.dumps({'source_id':10,'building_type_id':30,'state':2,'child_villager_ids':[2]}))
        self.assertEqual(code,200)
        self.now+=3600
        code,value=self.dispatch('game/village/collect_report_cards',building_id=10)
        self.assertEqual(code,200);self.assertIn('game_state',value);self.assertEqual(value['report_cards']['2']['stat'],'INT')
        self.assertEqual(self.dispatch('game/village/collect_report_cards',building_id=10)[1]['report_cards'],{})

    def test_native_tool_research_then_resource_purchase_survives_restart(self):
        rule=g.RULES['items']['377']
        d=copy.deepcopy(self.state.data)
        temple=d['game_state']['buildings']['1']
        temple['state']=int(next(k for k,v in g.RULES['buildings']['1']['state_data'].items()
                                if v.get('temple_level')==rule['research_temple_level'] and not v.get('buildable')))
        g.synchronize(d,self.now)
        d['game_state']['resources']['4']['count']=1000
        d['game_state']['resources']['1']['count']=100
        d['game_state']['resources']['2']['count']=100
        self.state.persist(d)
        code,value=self.dispatch('game/purchase/unlock_item',item_id=377)
        self.assertEqual(code,200)
        self.assertIn('377',value['unlock_information']['unlocked_item_cursors'])
        self.assertEqual(value['resources']['4']['count'],1000-rule['research_points'])
        code,value=self.dispatch('game/purchase/buy_item',item_id=377,count=1,use_points='false')
        self.assertEqual(code,200)
        self.assertEqual(value['items']['377']['count'],1)
        self.assertEqual(value['resources']['1']['count'],95)
        self.assertEqual(value['resources']['2']['count'],90)
        reloaded=server.State(self.temp.name,self.state.seed)
        self.assertEqual(reloaded.data['game_state']['items']['377']['count'],1)
        self.assertIn('377',reloaded.data['game_state']['unlock_information']['unlocked_item_cursors'])

    def test_food_route_charges_per_minute_and_repeated_poll_is_not_charged_twice(self):
        self.now=self.state.data['local_food']['last_charged_at']+60
        before=self.state.data['game_state']['resources']['3']['count']
        code,value=self.dispatch('game/village/consume_food')
        self.assertEqual(code,200)
        self.assertEqual(value['rate'],2)
        self.assertEqual(value['game_state']['resources']['3']['count'],before-2)
        self.assertEqual(self.dispatch('game/village/consume_food'),(code,value))

