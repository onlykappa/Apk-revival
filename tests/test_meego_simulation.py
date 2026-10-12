"""Private-file simulation parity checks; fixed clocks are explicit test inputs."""
import copy,json,os,pathlib,plistlib,tempfile,unittest,zipfile
from apk_revival.meego.engine import server,simulation as sim,local_game as g

def params(**values):return {k:[str(v)] for k,v in values.items()}

@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'),'Requires privately owned bundled Meego rules')
class MeegoSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as z:tree=plistlib.loads(z.read('assets/TechTree.plist'))['techtree']
        g.RULES={k:tree[k] for k in ['buildings','items','jobs','points_store']}
        seed=json.loads((pathlib.Path(__file__).resolve().parents[1]/'resources/meego-starter.json').read_text());self.state=server.State(self.temp.name,seed);self.data=copy.deepcopy(self.state.data);self.now=self.data['last_simulated_at']
    def tearDown(self):self.temp.cleanup()
    def test_gathering_caps_depletion_construction_and_restart(self):
        d=sim.mutate(self.data,'game/village/place_resource',params(building_type_id=3,location=3845),self.now);tree=next(b for b in d['game_state']['buildings'].values() if b['building_type']==3);d['game_state']['resources']['2']['count']=100
        d=sim.mutate(d,'game/village/set_job',params(villager_id=1,job_id=17,job_data=json.dumps({'source_id':tree['building_id'],'destination_id':1})),self.now);d=sim.advance(d,self.now+20);self.assertEqual(d['game_state']['resources']['2']['count'],130);self.assertEqual(d['game_state']['buildings'][str(tree['building_id'])]['count'],470);self.assertEqual(sim.advance(d,self.now+20),d)
        capped=copy.deepcopy(d);capped['game_state']['resources']['2']['count']=499;capped=sim.advance(capped,self.now+40);self.assertEqual(capped['game_state']['resources']['2']['count'],500)
        depleted=copy.deepcopy(d);depleted['game_state']['buildings'][str(tree['building_id'])]['count']=1;depleted=sim.advance(depleted,self.now+40);self.assertNotIn(str(tree['building_id']),depleted['game_state']['buildings'])
        d=sim.mutate(d,'game/village/place_building',params(building_type_id=5,location=676,orientation=1),self.now+20);hut=next(b for b in d['game_state']['buildings'].values() if b['building_type']==5);self.assertEqual(hut['state'],0);d=sim.mutate(d,'game/village/set_job',params(villager_id=2,job_id=5,job_data=json.dumps({'source_id':hut['building_id']})),self.now+20);d=sim.advance(d,self.now+80);self.assertEqual(d['game_state']['buildings'][str(hut['building_id'])]['state'],1);self.assertEqual(d['game_state']['all_villagers']['2']['job']['job_id'],0)
        self.state.persist(d);self.assertEqual(server.State(self.temp.name,self.state.seed).data,d)
    def test_breeding_is_idempotent_and_aging_is_bounded(self):
        d=sim.mutate(self.data,'game/village/place_building',params(building_type_id=5,location=676,orientation=1),self.now);hut=next(b for b in d['game_state']['buildings'].values() if b['building_type']==5);d['game_state']['buildings'][str(hut['building_id'])]['state']=21
        d=sim.mutate(d,'game/village/check_breeding_compatibility',params(father_id=1,mother_id=2),self.now);token=d['response_token'];d=sim.mutate(d,'game/village/breed',params(father_id=1,mother_id=2,token=token),self.now);self.assertEqual(len(d['game_state']['all_villagers']),3);self.assertEqual(sim.mutate(d,'game/village/breed',params(father_id=1,mother_id=2,token=token),self.now),d)
        d=sim.advance(d,self.now+7201);self.assertEqual(d['game_state']['all_villagers']['3']['job']['job_id'],2);d=sim.advance(d,self.now+36001);self.assertEqual(d['game_state']['all_villagers']['3']['job']['job_id'],0)
        with self.assertRaises(g.ActionError):sim.mutate(d,'game/village/set_job',params(villager_id=1,job_id=999),self.now+36001)
