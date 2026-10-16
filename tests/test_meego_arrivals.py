"""Deterministic offline newcomer tests; no private APK or live saves needed."""
import copy
import json
import unittest

from apk_revival.meego.engine import community as c, local_game as g


class MeegoArrivalTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000000
        self.rules = {'client_data': {
            '0': {'max_villager_count': 25},
            '7': {'villager_names': {'male': ['Mert', 'Jerf'],
                                     'female': ['Nooni', 'Derpina']}}}}
        self.data = {'game_user': {'user_id': 7},
                     'game_state': {'all_villagers': {}, 'points': 0},
                     'backend_probe': {'nonce': 'keep'},
                     'breeding_tokens': {'token': {'parents': [1, 2]}},
                     'local_migrations': ['starter-economy-1']}
        self.add_person(1)
        self.add_person(2)

    def add_person(self, ident, *, owner=7, dead=False, away=False, key=None):
        p = g.villager(ident, 'Existing', 1, c.APPEARANCE[1], owner, self.now)
        if dead:
            p['job']['job_id'] = 6
        if away:
            p['location_id'] = 999
        self.data['game_state']['all_villagers'][str(ident) if key is None else key] = p
        return p

    def advance(self, now, capacity=5, **kwargs):
        return c.advance(self.data, now, housing_capacity=capacity,
                         rules=self.rules, **kwargs)

    def test_existing_save_migration_waits_full_real_six_hours(self):
        before = copy.deepcopy(self.data)
        self.assertIsNone(self.advance(self.now))
        self.assertEqual(self.data['game_state'], before['game_state'])
        self.assertFalse(self.data[c.STATE_KEY]['original_server_policy_verified'])
        self.assertIsNone(self.advance(self.now + c.INTERVAL_SECONDS - 1))
        ident = self.advance(self.now + c.INTERVAL_SECONDS)
        self.assertEqual(ident, 3)
        self.assertEqual(len(self.data['game_state']['all_villagers']), 3)
        self.assertIsNone(self.advance(self.now + c.INTERVAL_SECONDS))

    def test_native_complete_owned_adult_and_slow_age_scale(self):
        self.advance(self.now)
        when = self.now + c.INTERVAL_SECONDS
        ident = self.advance(when, hours_per_age=2)
        person = self.data['game_state']['all_villagers'][str(ident)]
        self.assertEqual((person['user_id'], person['location_id'], person['location_type']), (7, 7, 0))
        self.assertEqual(person['birthday'], when - 20 * 2 * 3600)
        self.assertEqual(person['deathday'], when + 80 * 2 * 3600)
        self.assertEqual(person['job'], g.idle_job(when))
        self.assertEqual(person['name'], 'Mert')
        self.assertEqual(person['stats']['strength'], 10)
        self.assertEqual([i['item_id'] for i in person['appearance_items']], list(c.APPEARANCE[1]))
        self.assertTrue(all(i['count'] == 1 for i in person['appearance_items']))
        ident = self.advance(when + c.INTERVAL_SECONDS)
        self.assertEqual(self.data['game_state']['all_villagers'][str(ident)]['name'], 'Nooni')

    def test_offline_absence_adds_one_and_json_restart_preserves_deadline(self):
        self.advance(self.now)
        when = self.now + 30 * c.INTERVAL_SECONDS
        self.assertEqual(self.advance(when), 3)
        self.assertEqual(self.data[c.STATE_KEY]['next_due'], when + c.INTERVAL_SECONDS)
        self.data = json.loads(json.dumps(self.data))
        before = copy.deepcopy(self.data)
        self.assertIsNone(self.advance(when))
        self.assertEqual(self.data, before)
        self.assertIsNone(self.advance(when + 1))
        self.assertEqual(self.advance(when + c.INTERVAL_SECONDS), 4)

    def test_full_capacity_discards_due_opportunity_without_queued_burst(self):
        self.advance(self.now, capacity=2)
        when = self.now + 20 * c.INTERVAL_SECONDS
        self.assertIsNone(self.advance(when, capacity=2))
        self.assertEqual(self.data[c.STATE_KEY]['next_due'], when + c.INTERVAL_SECONDS)
        self.assertIsNone(self.advance(when + 1, capacity=5))
        self.assertEqual(self.advance(when + c.INTERVAL_SECONDS, capacity=5), 3)
        self.assertIsNone(self.advance(when + c.INTERVAL_SECONDS, capacity=5))

    def test_guests_and_dead_keep_models_but_owned_travellers_reserve_beds(self):
        guest = copy.deepcopy(self.add_person(10, owner=8))
        dead = copy.deepcopy(self.add_person(11, dead=True))
        traveller = copy.deepcopy(self.add_person(12, away=True))
        self.advance(self.now, capacity=3)
        when = self.now + c.INTERVAL_SECONDS
        self.assertIsNone(self.advance(when, capacity=3))
        self.assertEqual(self.advance(when + c.INTERVAL_SECONDS, capacity=4), 13)
        people = self.data['game_state']['all_villagers']
        self.assertEqual(people['10'], guest)
        self.assertEqual(people['11'], dead)
        self.assertEqual(people['12'], traveller)

    def test_original_population_ceiling_and_lower_bundled_limit(self):
        for ident in range(3, 26):
            self.add_person(ident)
        self.advance(self.now, capacity=100)
        self.assertIsNone(self.advance(self.now + c.INTERVAL_SECONDS, capacity=100))
        self.assertEqual(len(self.data['game_state']['all_villagers']), 25)
        self.data['game_state']['all_villagers'] = {k: p for k, p in self.data['game_state']['all_villagers'].items() if int(k) <= 2}
        self.rules['client_data']['0']['max_villager_count'] = 2
        self.assertIsNone(self.advance(self.now + 2 * c.INTERVAL_SECONDS, capacity=100))

    def test_id_collision_checks_keys_models_and_persisted_cursor(self):
        unusual = copy.deepcopy(self.add_person(40, key='legacy-record'))
        self.add_person(3, key='100')
        self.advance(self.now)
        self.assertEqual(self.data[c.STATE_KEY]['next_villager_id'], 101)
        self.add_person(201)
        when = self.now + c.INTERVAL_SECONDS
        self.assertEqual(self.advance(when, capacity=10), 202)
        del self.data['game_state']['all_villagers']['202']
        self.data = json.loads(json.dumps(self.data))
        self.assertEqual(self.advance(when + c.INTERVAL_SECONDS, capacity=10), 203)
        self.assertEqual(self.data['game_state']['all_villagers']['legacy-record'], unusual)

    def test_unrelated_backend_data_and_existing_controls_remain_unchanged(self):
        before = copy.deepcopy(self.data)
        self.advance(self.now)
        self.advance(self.now + c.INTERVAL_SECONDS)
        for key in ('backend_probe', 'breeding_tokens', 'local_migrations', 'game_user'):
            self.assertEqual(self.data[key], before[key])
        for key, person in before['game_state']['all_villagers'].items():
            self.assertEqual(self.data['game_state']['all_villagers'][key], person)
        self.assertEqual(self.data['game_state']['points'], 0)
        self.assertNotIn(c.STATE_KEY, self.data['game_state'])

    def test_clock_rollback_and_invalid_configuration_never_add_people(self):
        self.advance(self.now)
        before = copy.deepcopy(self.data)
        self.assertIsNone(self.advance(self.now - c.INTERVAL_SECONDS))
        self.assertEqual(self.data, before)
        for kwargs in ({'now': float('nan')}, {'now': self.now + 1, 'capacity': -1},
                       {'now': self.now + 1, 'hours_per_age': 0}):
            with self.assertRaises(ValueError):
                self.advance(**kwargs)
            self.assertEqual(self.data, before)


if __name__ == '__main__':
    unittest.main()
