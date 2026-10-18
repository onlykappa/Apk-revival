"""Aging/deadline regressions with fixed clocks and authored village rules."""
import copy
import json
import unittest

from apk_revival.meego.engine import local_game as g, simulation as sim


class AgingTests(unittest.TestCase):
    def setUp(self):
        self.old_rules = g.RULES
        g.RULES = {'buildings': {'1': {'size': 2, 'state_data': {'1': {
            'villager_slots': 5, 'resource_caps': {str(i): 500 for i in range(1, 6)}}}}},
            'jobs': {'0': {'type': 0}, '1': {'type': 5}, '2': {'type': 6},
                     '3': {'type': 1}, '6': {'type': 8}}, 'items': {}, 'points_store': {}}
        self.now = 1_000_000
        self.data = {'game_user': {'user_id': 7}, 'last_simulated_at': self.now,
            'local_migrations': ['starter-economy-1', 'completed-trips-2'],
            'game_state': {'all_villagers': {}, 'buildings': {'1': g.building(1, 1, 1, 100, self.now)},
                'resources': {str(i): {'resource_id': i, 'count': 100, 'last_update': self.now} for i in range(1, 6)},
                'global_state': {}, 'points': 0, 'achievements': {}, 'unlock_information': {'unlocked_item_cursors': []}}}
        mother = g.villager(1, 'Mother', 0, [], 7, self.now)
        baby = g.villager(2, 'Baby', 1, [], 7, self.now)
        baby.update(birthday=self.now, deathday=self.now + 100 * 3600)
        mother['job'].update(job_id=3, target_id=2)
        baby['job'].update(job_id=1, target_id=1)
        self.data['game_state']['all_villagers'].update({'1': mother, '2': baby})

    def tearDown(self):
        g.RULES = self.old_rules

    def test_nursing_deadline_does_not_restart_at_each_ten_second_poll(self):
        deadline = self.now + sim.SETTINGS['baby_age'] * 3600
        data = sim.advance(self.data, self.now + .1)
        for offset in (10.2, 20.8, 60.1, 130.9):
            data = json.loads(json.dumps(sim.advance(data, self.now + offset)))
            for ident in ('1', '2'):
                job = data['game_state']['all_villagers'][ident]['job']
                self.assertEqual(job['last_update'] + job['update_interval'], deadline)
            self.assertEqual(data['game_state']['all_villagers']['2']['birthday'], self.now)

    def test_native_job_update_cannot_reset_nursing_or_childhood(self):
        for kind, age in ((1, sim.SETTINGS['baby_age']), (2, sim.SETTINGS['adult_age'])):
            data = copy.deepcopy(self.data)
            data['game_state']['all_villagers']['2']['job']['job_id'] = kind
            updated = sim.mutate(data, 'game/village/update_villager_job', {'villager_id': ['2']}, self.now + 30.5)
            job = updated['game_state']['all_villagers']['2']['job']
            self.assertEqual(job['last_update'] + job['update_interval'], self.now + age * 3600)

    def test_baby_grows_and_releases_parent_then_child_becomes_adult(self):
        data = sim.advance(self.data, self.now + sim.SETTINGS['baby_age'] * 3600)
        people = data['game_state']['all_villagers']
        self.assertEqual(people['1']['job']['job_id'], 0)
        self.assertEqual(people['2']['job']['job_id'], 2)
        child_job = people['2']['job']
        self.assertEqual(child_job['last_update'] + child_job['update_interval'], self.now + sim.SETTINGS['adult_age'] * 3600)
        data = sim.advance(json.loads(json.dumps(data)), self.now + sim.SETTINGS['adult_age'] * 3600)
        self.assertEqual(data['game_state']['all_villagers']['2']['job']['job_id'], 0)
        self.assertEqual(data['game_state']['all_villagers']['2']['birthday'], self.now)

    def test_offline_restart_can_cross_both_growth_boundaries(self):
        data = sim.advance(json.loads(json.dumps(self.data)), self.now + 12 * 3600)
        self.assertEqual(data['game_state']['all_villagers']['2']['job']['job_id'], 0)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)
        self.assertEqual(sim.advance(data, self.now + 12 * 3600), data)

    def test_individual_deathday_is_used_and_dead_people_do_not_consume_food(self):
        data = copy.deepcopy(self.data)
        for person in data['game_state']['all_villagers'].values():
            person['deathday'] = self.now + 30
        data = sim.advance(data, self.now + 29)
        self.assertTrue(all(p['job']['job_id'] != 6 for p in data['game_state']['all_villagers'].values()))
        data = sim.advance(data, self.now + 30)
        self.assertTrue(all(p['job']['job_id'] == 6 for p in data['game_state']['all_villagers'].values()))
        self.assertEqual(data['game_state']['global_state']['food_consumption_rate'], 0)

    def test_starter_factory_uses_same_hour_scale_as_native_configuration(self):
        person = g.villager(9, 'Starter', 1, [], 7, self.now)
        self.assertEqual(sim.hours_age(person, self.now), 20)
        self.assertEqual(person['deathday'], self.now + 80 * 3600)

    def test_one_day_offline_adds_twelve_age_hours_and_preserves_lifespan(self):
        person=self.data['game_state']['all_villagers']['1']
        original=copy.deepcopy(person)
        result=sim.advance(self.data,self.now+86400,offline=True,food_active=False)
        aged=result['game_state']['all_villagers']['1']
        self.assertEqual(sim.hours_age(aged,self.now+86400)-sim.hours_age(original,self.now),12)
        self.assertEqual(aged['deathday']-aged['birthday'],original['deathday']-original['birthday'])
        self.assertEqual(person,original)
        self.assertEqual(aged['deathday'],original['deathday']+43200)

    def test_active_play_keeps_existing_aging_rate(self):
        result=sim.advance(self.data,self.now+3600)
        self.assertEqual(sim.hours_age(result['game_state']['all_villagers']['1'],self.now+3600),21)

    def test_closed_polling_restart_and_repeated_time_never_double_apply(self):
        single=sim.advance(self.data,self.now+86400,offline=True,food_active=False)
        many=self.data
        for hour in (1,4,12,24):
            many=sim.advance(json.loads(json.dumps(many)),self.now+hour*3600,offline=True,food_active=False)
        for ident in ('1','2'):
            for key in ('birthday','deathday'):
                self.assertEqual(many['game_state']['all_villagers'][ident][key],single['game_state']['all_villagers'][ident][key])
        self.assertEqual(sim.advance(single,self.now+86400,offline=True,food_active=False),single)
        rolled=sim.advance(single,self.now+86300,offline=True,food_active=False)
        self.assertEqual(rolled['game_state']['all_villagers']['1']['birthday'],single['game_state']['all_villagers']['1']['birthday'])

    def test_offline_growth_and_native_nursing_countdown_use_same_age(self):
        data=sim.advance(self.data,self.now+2*3600,offline=True,food_active=False)
        people=data['game_state']['all_villagers']
        self.assertEqual(people['2']['job']['job_id'],1)
        job=people['2']['job']
        self.assertEqual(job['last_update']+job['update_interval'],self.now+3*3600)
        data=sim.advance(data,self.now+4*3600,offline=True,food_active=False)
        self.assertEqual(data['game_state']['all_villagers']['2']['job']['job_id'],2)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'],0)

    def test_long_absence_is_halved_before_work_catchup_limit(self):
        data=sim.advance(self.data,self.now+4*86400,offline=True,food_active=False)
        self.assertEqual(sim.hours_age(data['game_state']['all_villagers']['1'],self.now+4*86400),68)

    def test_already_dead_people_and_unowned_guests_are_not_rejuvenated(self):
        people=self.data['game_state']['all_villagers']
        people['1']['job']['job_id']=6
        people['2']['user_id']=999
        original=copy.deepcopy(people)
        result=sim.advance(self.data,self.now+3600,offline=True,food_active=False)
        for ident in people:
            self.assertEqual(result['game_state']['all_villagers'][ident]['birthday'],original[ident]['birthday'])

    def test_growth_skip_token_stays_valid_across_offline_age_adjustment(self):
        from apk_revival.meego.engine import mods
        token=next(t['token'] for t in mods.timers(self.data,self.now) if t['kind']=='growth')
        data=sim.advance(self.data,self.now+100,offline=True,food_active=False)
        result,_=mods.skip(data,token,self.now+100)
        self.assertEqual(result['game_state']['all_villagers']['2']['job']['job_id'],2)

    def test_adventure_render_snapshot_uses_same_dates_as_home(self):
        from apk_revival.meego.engine import aging,adventures
        self.data[adventures.KEY]={'sessions':{'1':{'game_state':{'all_villagers':copy.deepcopy(self.data['game_state']['all_villagers'])}}}}
        aging.slow_offline(self.data,self.now,self.now+100)
        snapshot=self.data[adventures.KEY]['sessions']['1']['game_state']['all_villagers']
        self.assertEqual(snapshot['1']['birthday'],self.data['game_state']['all_villagers']['1']['birthday'])

    def test_server_restart_first_poll_and_logout_resume_apply_half_only_offline(self):
        import tempfile
        from unittest.mock import patch
        from pathlib import Path
        from apk_revival.meego.engine import server
        seed=copy.deepcopy(self.data)
        seed['format_version']=1
        seed['game_state']['name']='local'
        with tempfile.TemporaryDirectory() as directory:
            server.atomic_json(Path(directory)/'saves/village.json',seed)
            with patch.object(server.time,'time',return_value=self.now+3600):
                state=server.State(directory,seed)
                state.handle('game/village/get_village',{})
                self.assertEqual(sim.hours_age(state.data['game_state']['all_villagers']['1'],self.now+3600),20.5)
            with patch.object(server.time,'time',return_value=self.now+7200):
                state.handle('game/logout',{})
                self.assertEqual(sim.hours_age(state.data['game_state']['all_villagers']['1'],self.now+7200),21.5)
            with patch.object(server.time,'time',return_value=self.now+14400):
                state.handle('game/login/resume_connection',{})
                self.assertEqual(sim.hours_age(state.data['game_state']['all_villagers']['1'],self.now+14400),22.5)


if __name__ == '__main__':
    unittest.main()
