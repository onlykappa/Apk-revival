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


if __name__ == '__main__':
    unittest.main()
