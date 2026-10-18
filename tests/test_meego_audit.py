"""Confirmed model-removal and resource-move regressions from the 0.9.4 audit."""
import copy
import unittest
from unittest.mock import patch

from apk_revival.meego.engine import ecology, local_game as g, relocation, server


def params(**values):
    return {key: [str(value)] for key, value in values.items()}


class MeegoAuditTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000000
        self.rules = {'buildings': {
            '1': {'size': 2, 'state_data': {'1': {'temple_level': 2}}},
            '2': {'size': 2, 'state_data': {'1': {}}},
            '5': {'size': 2, 'state_data': {'1': {'can_user_delete': True}}},
        }}
        self.patch = patch.object(g, 'RULES', self.rules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.data = {'game_user': {'user_id': 7},
            'game_state': {'name': 'local', 'all_villagers': {},
                'buildings': {'1': g.building(1, 1, 1, 0, self.now),
                              '2': g.building(2, 2, 1, 200, self.now)},
                'items': {}, 'resources': {}}}
        person = g.villager(7, 'Worker', 1, [], 7, self.now)
        person['job'].update(job_id=16, source_id=2, target_id=2, destination_id=1)
        self.data['game_state']['all_villagers']['7'] = person

    def test_resource_delete_explicitly_clears_native_model_and_stops_worker(self):
        before = copy.deepcopy(self.data)
        result = g.mutate(self.data, 'game/village/delete_resource_building', params(location=200), self.now)
        projected = server.native_payload(result['game_state'], depleted_nodes=relocation.removed_nodes(result))
        self.assertIsNone(projected['buildings']['2'])
        self.assertEqual(projected['all_villagers']['7']['job']['job_id'], 0)
        self.assertEqual(self.data, before)
        # A future reused ID is a real model, never overwritten by a tombstone.
        result['game_state']['buildings']['2'] = g.building(2, 2, 1, 300, self.now)
        self.assertIsNotNone(server.native_payload(result['game_state'], depleted_nodes=relocation.removed_nodes(result))['buildings']['2'])

    def test_deleted_structure_clears_model_and_its_depot_workers(self):
        self.data['game_state']['buildings']['5'] = g.building(5, 5, 1, 400, self.now)
        self.data['game_state']['all_villagers']['7']['job']['destination_id'] = 5
        result = g.mutate(self.data, 'game/village/delete_building', params(building_id=5), self.now)
        projected = server.native_payload(result['game_state'], depleted_nodes=relocation.removed_nodes(result))
        self.assertIsNone(projected['buildings']['5'])
        self.assertEqual(projected['all_villagers']['7']['job']['job_id'], 0)

    def test_resource_move_preserves_remaining_stock_without_duplicating_capacity(self):
        node = self.data['game_state']['buildings']['2']
        node['count'] = 100  # Partially harvested 300-capacity level-two rock.
        ecology.register_stock(self.data, node, 300)
        relocation.move(self.data, '2', 300, 1, self.now)
        ecology.upgrade_resource_stocks(self.data, self.rules)
        self.assertEqual(self.data['game_state']['buildings']['300']['count'], 100)
        self.assertNotIn('2', self.data[ecology.CAPACITY_KEY])
        self.assertEqual(self.data[ecology.CAPACITY_KEY]['300']['location'], 300)
        self.assertEqual(self.data['game_state']['all_villagers']['7']['job']['source_id'], 300)
        self.rules['buildings']['1']['state_data']['1']['temple_level'] = 3
        ecology.upgrade_resource_stocks(self.data, self.rules)
        self.assertEqual(self.data['game_state']['buildings']['300']['count'], 150)
        ecology.upgrade_resource_stocks(self.data, self.rules)
        self.assertEqual(self.data['game_state']['buildings']['300']['count'], 150)

    def test_move_same_model_identity_updates_capacity_location(self):
        node = self.data['game_state']['buildings']['2']
        node['count'] = 80
        ecology.register_stock(self.data, node, 300)
        relocation.move(self.data, '2', 2, 1, self.now)
        ecology.upgrade_resource_stocks(self.data, self.rules)
        self.assertEqual(node['count'], 80)

    def test_removal_history_is_bounded(self):
        for ident in range(600):
            relocation.remember_removal(self.data, ident, self.now + ident)
        self.assertEqual(len(self.data[relocation.REMOVED_KEY]), 512)
        self.assertNotIn('0', self.data[relocation.REMOVED_KEY])
