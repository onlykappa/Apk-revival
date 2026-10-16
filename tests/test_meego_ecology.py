"""Bounded resource replenishment using synthetic private-save snapshots."""
import copy
import json
import unittest

from apk_revival.meego.engine import ecology as e, local_game as g


class MeegoEcologyTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000
        self.rules = {'buildings': {
            str(kind): {'size': size, 'default_state': 1}
            for kind, size in ((1, 5), (2, 3), (3, 2), (4, 2), (5, 2))}}
        self.data = {'game_state': {'buildings': {},
                                    'resources': {'3': {'count': 17}},
                                    'all_villagers': {'keep': {'name': 'Existing'}}},
                     'breeding_tokens': {'keep': 'unchanged'}}
        self.add(1, 1, 0)
        self.add(2, 2, 10 * g.MAP_SIZE + 10)
        self.add(3, 3, 20 * g.MAP_SIZE + 20)
        self.add(4, 4, 30 * g.MAP_SIZE + 30)

    def add(self, ident, kind, location, key=None):
        self.data['game_state']['buildings'][str(ident) if key is None else key] = (
            g.building(ident, kind, 1, location, self.now))

    def advance(self, now):
        return e.advance(self.data, now, rules=self.rules)

    def test_migration_preserves_village_and_waits_full_interval(self):
        before = copy.deepcopy(self.data)
        self.assertIsNone(self.advance(self.now))
        self.assertEqual(self.data['game_state'], before['game_state'])
        self.assertFalse(self.data[e.STATE_KEY]['original_server_timing_verified'])
        self.assertNotIn(e.STATE_KEY, self.data['game_state'])
        del self.data['game_state']['buildings']['2']
        self.assertIsNone(self.advance(self.now + e.INTERVAL_SECONDS - 1))
        ident = self.advance(self.now + e.INTERVAL_SECONDS)
        node = self.data['game_state']['buildings'][str(ident)]
        self.assertEqual((node['building_type'], node['location'], node['count']),
                         (2, 10 * g.MAP_SIZE + 10, 40))
        self.assertEqual(set(node), set(g.building(1, 2, 1, 0, 0)))

    def test_empty_migration_never_guesses_off_island_coordinates(self):
        self.data['game_state']['buildings'] = {'1': self.data['game_state']['buildings']['1']}
        self.advance(self.now)
        self.assertIsNone(self.advance(self.now + 30 * e.INTERVAL_SECONDS))
        self.assertEqual(len(self.data['game_state']['buildings']), 1)

    def test_long_absence_adds_one_node_and_json_restart_keeps_deadline(self):
        self.advance(self.now)
        for ident in ('2', '3', '4'):
            del self.data['game_state']['buildings'][ident]
        when = self.now + 200 * e.INTERVAL_SECONDS
        self.assertEqual(self.advance(when), 5)
        self.data = json.loads(json.dumps(self.data))
        before = copy.deepcopy(self.data)
        self.assertIsNone(self.advance(when))
        self.assertEqual(self.data, before)
        self.assertIsNone(self.advance(when + 1))
        self.assertEqual(self.advance(when + e.INTERVAL_SECONDS), 6)
        self.assertEqual(self.data['game_state']['buildings']['6']['building_type'], 3)

    def test_occupied_sites_skipped_and_full_map_does_not_overwrite_buildings(self):
        self.advance(self.now)
        del self.data['game_state']['buildings']['2']
        del self.data['game_state']['buildings']['3']
        self.add(5, 5, 10 * g.MAP_SIZE + 10)
        occupied = copy.deepcopy(self.data['game_state']['buildings']['5'])
        ident = self.advance(self.now + e.INTERVAL_SECONDS)
        self.assertEqual(self.data['game_state']['buildings'][str(ident)]['building_type'], 3)
        self.assertEqual(self.data['game_state']['buildings']['5'], occupied)
        # Fill all known sites and remove the remaining resource models.
        buildings = self.data['game_state']['buildings']
        for key in list(buildings):
            if buildings[key]['building_type'] in e.RESOURCE_LIMITS:
                del buildings[key]
        self.add(20, 5, 20 * g.MAP_SIZE + 20)
        self.add(21, 5, 30 * g.MAP_SIZE + 30)
        before = copy.deepcopy(buildings)
        when = self.now + 2 * e.INTERVAL_SECONDS
        self.assertIsNone(self.advance(when))
        self.assertEqual(buildings, before)
        self.assertEqual(self.data[e.STATE_KEY]['next_due'], when + e.INTERVAL_SECONDS)

    def test_existing_nodes_stocks_bank_and_controls_untouched(self):
        before = copy.deepcopy(self.data)
        self.advance(self.now)
        self.advance(self.now + e.INTERVAL_SECONDS)
        for key, value in before['game_state']['buildings'].items():
            self.assertEqual(self.data['game_state']['buildings'][key], value)
        for key in ('resources', 'all_villagers'):
            self.assertEqual(self.data['game_state'][key], before['game_state'][key])
        self.assertEqual(self.data['breeding_tokens'], before['breeding_tokens'])

    def test_original_pool_ceiling_and_lower_private_rule_ceiling(self):
        for ident, location in ((5, 12), (6, 18), (7, 24)):
            self.add(ident, 2, 10 * g.MAP_SIZE + location)
        self.advance(self.now)
        self.data[e.STATE_KEY]['sites'].append({'kind': 2, 'location': 40 * g.MAP_SIZE + 40, 'orientation': 0})
        # Other types can replenish; the four-rock ceiling must remain.
        self.advance(self.now + e.INTERVAL_SECONDS)
        self.assertEqual(sum(b['building_type'] == 2 for b in self.data['game_state']['buildings'].values()), 4)
        self.rules['client_data'] = {'0': {'resource_buildings': {'2': 1, '3': 1, '4': 1}}}
        before = copy.deepcopy(self.data['game_state']['buildings'])
        self.assertIsNone(self.advance(self.now + 2 * e.INTERVAL_SECONDS))
        self.assertEqual(self.data['game_state']['buildings'], before)

    def test_native_placed_sites_are_learned_before_future_depletion(self):
        self.advance(self.now)
        location = 40 * g.MAP_SIZE + 40
        self.add(5, 4, location)
        self.advance(self.now + 1)
        self.assertIn({'kind': 4, 'location': location, 'orientation': 0}, self.data[e.STATE_KEY]['sites'])
        for ident in ('2', '3', '4', '5'):
            del self.data['game_state']['buildings'][ident]
        self.data[e.STATE_KEY]['next_kind'] = 4
        ident = self.advance(self.now + e.INTERVAL_SECONDS)
        self.assertEqual(self.data['game_state']['buildings'][str(ident)]['count'], 75)

    def test_ids_consider_native_models_dictionary_keys_and_persisted_cursor(self):
        self.add(30, 5, 60 * g.MAP_SIZE + 60, key='legacy-model')
        self.add(20, 5, 55 * g.MAP_SIZE + 55, key='100')
        self.advance(self.now)
        del self.data['game_state']['buildings']['2']
        ident = self.advance(self.now + e.INTERVAL_SECONDS)
        self.assertEqual(ident, 101)
        del self.data['game_state']['buildings']['101']
        self.assertEqual(self.advance(self.now + 2 * e.INTERVAL_SECONDS), 102)

    def test_clock_rollback_and_invalid_values_do_not_change_save(self):
        self.advance(self.now)
        before = copy.deepcopy(self.data)
        self.assertIsNone(self.advance(self.now - 1))
        self.assertEqual(self.data, before)
        for value in (float('nan'), float('inf'), True, 'invalid'):
            with self.assertRaises(ValueError):
                self.advance(value)
            self.assertEqual(self.data, before)
        with self.assertRaises(ValueError):
            e.advance(self.data, self.now + 1, rules=self.rules, stocks={2: 40, 3: 30, 4: 0})
        self.assertEqual(self.data, before)


if __name__ == '__main__':
    unittest.main()
