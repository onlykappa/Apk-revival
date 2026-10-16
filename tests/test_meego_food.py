"""Minute-rate food conservation using synthetic snapshots, never live saves."""
import copy
import json
import unittest

from apk_revival.meego.engine import food as f, local_game as g


class MeegoFoodTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000
        self.data = {'game_user': {'user_id': 7},
                     'game_state': {'all_villagers': {},
                                    'resources': {'3': {'count': 100, 'last_update': self.now}},
                                    'global_state': {'food_consumption_rate': 0},
                                    'buildings': {'keep': {'location': 4}}},
                     'backend_probe': {'nonce': 'preserve'}}
        self.add(1)
        self.add(2)
        # Initialize prospectively, as a newly created local village does.
        f.advance(self.data, self.now, self.now)

    def add(self, ident, *, owner=7, location=7, location_type=0, job=0):
        person = g.villager(ident, 'Existing', 1, [], owner, self.now)
        person.update(location_id=location, location_type=location_type)
        person['job']['job_id'] = job
        self.data['game_state']['all_villagers'][str(ident)] = person
        return person

    def test_two_residents_consume_two_per_minute_with_matching_native_rate(self):
        consumed = f.advance(self.data, self.now, self.now + 60)
        self.assertEqual(consumed, 2)
        self.assertEqual(self.data['game_state']['resources']['3']['count'], 98)
        self.assertEqual(self.data['game_state']['global_state']['food_consumption_rate'], 2)
        self.assertFalse(self.data[f.STATE_KEY]['original_server_policy_verified'])
        self.assertNotIn(f.STATE_KEY, self.data['game_state'])

    def test_fraction_does_not_round_away_under_frequent_polls_and_restarts(self):
        self.data['game_state']['all_villagers'].pop('2')
        for second in range(1, 61):
            f.advance(self.data, self.now + second - 1, self.now + second)
            self.data = json.loads(json.dumps(self.data))
        self.assertEqual(self.data['game_state']['resources']['3']['count'], 99)
        self.assertEqual(self.data['food_fraction'], 0)

    def test_subsecond_partition_matches_single_call_from_absolute_endpoints(self):
        initial = copy.deepcopy(self.data)
        previous = self.now
        for when in (self.now + .123456, self.now + 2.111111,
                     self.now + 19.012345, self.now + 60):
            f.advance(self.data, previous, when)
            previous = when
        f.advance(initial, self.now, self.now + 60)
        self.assertEqual(self.data['game_state']['resources'], initial['game_state']['resources'])
        self.assertEqual(self.data['food_fraction'], initial['food_fraction'])

    def test_guests_dead_away_and_dungeon_villagers_do_not_charge_home_food(self):
        self.add(3, owner=8)
        self.add(4, job=6)
        self.add(5, location=999)
        self.add(6, location_type=1)
        self.add(7, job=1)
        self.add(8, job=2)
        self.assertEqual(f.consumption_rate(self.data), 4)
        self.assertEqual(f.advance(self.data, self.now, self.now + 60), 4)

    def test_empty_stores_never_go_negative_or_charge_future_food_debt(self):
        self.data['game_state']['resources']['3']['count'] = 1
        self.assertEqual(f.advance(self.data, self.now, self.now + 10_000), 1)
        self.assertEqual(self.data['food_fraction'], 0)
        self.data['game_state']['resources']['3']['count'] = 10
        self.assertEqual(f.advance(self.data, self.now + 10_000, self.now + 10_015), 0)
        self.assertEqual(self.data['game_state']['resources']['3']['count'], 10)
        self.assertEqual(self.data['food_fraction'], .5)

    def test_repeated_requests_and_clock_rollback_do_not_double_charge(self):
        self.assertEqual(f.advance(self.data, self.now, self.now + 60), 2)
        self.assertEqual(f.advance(self.data, self.now, self.now + 60), 0)
        self.assertEqual(f.advance(self.data, self.now - 100, self.now + 30), 0)
        self.assertEqual(self.data['game_state']['resources']['3']['count'], 98)
        self.assertEqual(f.advance(self.data, self.now + 30, self.now + 120), 2)

    def test_legacy_fraction_preserved_without_retroactive_rate_migration(self):
        self.data.pop(f.STATE_KEY)
        self.data['food_fraction'] = .5
        self.assertEqual(f.advance(self.data, self.now - 86400, self.now), 0)
        self.assertEqual(self.data['game_state']['resources']['3']['count'], 100)
        self.assertEqual(self.data['food_fraction'], .5)
        self.assertEqual(f.advance(self.data, self.now, self.now + 15), 1)

    def test_offline_limit_and_rate_changes_use_only_the_current_interval(self):
        self.assertEqual(f.advance(self.data, self.now, self.now + 3600, maximum_elapsed=60), 2)
        self.data['game_state']['all_villagers']['2']['location_id'] = 999
        self.assertEqual(f.advance(self.data, self.now + 3600, self.now + 3660), 1)
        self.assertEqual(self.data['game_state']['global_state']['food_consumption_rate'], 1)

    def test_no_food_consumption_side_effects_on_people_buildings_or_backend(self):
        before = copy.deepcopy(self.data)
        f.advance(self.data, self.now, self.now + 60)
        for key in ('all_villagers', 'buildings'):
            self.assertEqual(self.data['game_state'][key], before['game_state'][key])
        self.assertEqual(self.data['backend_probe'], before['backend_probe'])

    def test_invalid_clocks_rate_or_fraction_leave_save_unchanged(self):
        before = copy.deepcopy(self.data)
        for kwargs in ({'now': float('nan')}, {'now': True}, {'maximum_elapsed': -1},
                       {'food_per_resident_per_minute': .5}):
            values = dict(previous=self.now, now=self.now + 60)
            values.update(kwargs)
            with self.assertRaises(ValueError):
                f.advance(self.data, **values)
            self.assertEqual(self.data, before)
        self.data['food_fraction'] = 1.2
        self.data.pop(f.STATE_KEY)
        before = copy.deepcopy(self.data)
        with self.assertRaises(ValueError):
            f.advance(self.data, self.now, self.now + 60)
        self.assertEqual(self.data, before)


if __name__ == '__main__':
    unittest.main()
