"""Closed-session food lifecycle checks against temporary original-rule saves."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apk_revival.meego.engine import food, local_game as g, server
import test_meego_mods as fixtures

@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires owned original APK')
class FoodSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SkipTimerTests.setUpClass()
        cls.rules=fixtures.SkipTimerTests.rules;cls.seed=fixtures.SkipTimerTests.seed

    def setUp(self):
        self.now=1000000
        self.rule_patch=patch.object(g,'RULES',copy.deepcopy(self.rules));self.rule_patch.start();self.addCleanup(self.rule_patch.stop)
        self.clock=patch.object(server.time,'time',return_value=self.now);self.time=self.clock.start();self.addCleanup(self.clock.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=server.State(self.temp.name,self.seed)
        self.state.data['game_state']['resources']['3']['count']=100
        food.resume(self.state.data,self.now)
        self.state.persist(self.state.data)
        self.state.handle('game/login/oauth',{})

    def test_online_food_charges_but_logged_out_polls_and_resume_do_not(self):
        self.time.return_value=self.now+60
        self.state.handle('game/village/get_resources',{})
        self.assertEqual(self.state.data['game_state']['resources']['3']['count'],98)
        self.state.handle('game/logout',{})
        self.time.return_value=self.now+3600
        self.state.handle('game/poll/notices',{})
        self.assertEqual(self.state.data['game_state']['resources']['3']['count'],98)
        self.time.return_value=self.now+7200
        self.state.handle('game/login/resume_connection',{})
        self.assertEqual(self.state.data['game_state']['resources']['3']['count'],98)
        self.time.return_value=self.now+7260
        self.state.handle('game/village/get_resources',{})
        self.assertEqual(self.state.data['game_state']['resources']['3']['count'],96)

    def test_unclean_restart_freezes_food_and_keeps_other_offline_aging(self):
        person=self.state.data['game_state']['all_villagers']['1']
        person['birthday']=self.now
        person['job']['job_id']=1
        self.state.data['game_state']['all_villagers']['2']['job'].update(job_id=3,target_id=1)
        self.state.persist(self.state.data)
        self.time.return_value=self.now+4*3600
        restarted=server.State(self.temp.name,self.seed)
        self.assertEqual(restarted.data['game_state']['resources']['3']['count'],100)
        self.assertEqual(restarted.data['last_simulated_at'],self.now)
        restarted.handle('game/login/oauth',{})
        self.assertEqual(restarted.data['game_state']['resources']['3']['count'],100)
        self.assertEqual(restarted.data['game_state']['all_villagers']['1']['job']['job_id'],2)
        self.assertEqual(restarted.data['game_state']['all_villagers']['2']['job']['job_id'],0)
        self.assertEqual(restarted.data['game_state']['global_state']['mood_state'],2)

    def test_restart_repairs_native_hunger_without_refilling_or_debiting_food(self):
        self.state.data['game_state']['global_state']['mood_state']=0
        self.state.data[food.STATE_KEY]['policy']=food.LEGACY_POLICY
        self.state.persist(self.state.data)
        self.time.return_value=self.now+2*86400
        restored=server.State(self.temp.name,self.seed)
        self.assertEqual(restored.data['game_state']['resources']['3']['count'],100)
        self.assertEqual(restored.data['game_state']['global_state']['mood_state'],2)
        snapshot=json.loads(restored.save.read_text())
        self.assertEqual(snapshot['game_state']['resources']['3']['count'],100)
        self.assertEqual(snapshot[food.STATE_KEY]['policy'],food.POLICY)

    def test_closed_food_harvest_pauses_without_losing_bush_stock_while_wood_advances(self):
        from apk_revival.meego.engine import simulation as sim
        gs=self.state.data['game_state']
        for ident,kind,count,location in ((90,4,75,3845),(91,3,30,500)):
            gs['buildings'][str(ident)]=g.building(ident,kind,1,location,self.now)
            gs['buildings'][str(ident)]['count']=count
            from apk_revival.meego.engine import ecology
            ecology.register_stock(self.state.data,gs['buildings'][str(ident)],250)
        for person,job,source in ((1,18,90),(2,17,91)):
            fields=dict(villager_id=[str(person)],job_id=[str(job)],job_data=[json.dumps(dict(source_id=source,destination_id=1))])
            self.state.data=sim.mutate(self.state.data,'game/village/set_job',fields,self.now)
        self.state.persist(self.state.data)
        self.state.handle('game/logout',{})
        self.time.return_value=self.now+60
        restarted=server.State(self.temp.name,self.seed)
        # Also cover the first request after restart without an explicit login.
        restarted.handle('game/village/get_village',{})
        saved=restarted.data['game_state']
        self.assertEqual(saved['resources']['3']['count'],100)
        self.assertEqual(saved['buildings']['90']['count'],75)
        self.assertGreater(saved['resources']['2']['count'],0)
        self.time.return_value=self.now+72
        restarted.handle('game/village/get_resources',{})
        self.assertGreater(restarted.data['game_state']['resources']['3']['count'],100)
        self.assertLess(restarted.data['game_state']['buildings']['90']['count'],75)

