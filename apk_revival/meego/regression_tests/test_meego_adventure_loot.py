import copy
import json
import unittest
from unittest.mock import patch

from apk_revival.meego.engine import adventure_loot as loot


class AdventureLootTests(unittest.TestCase):
    def setUp(self):
        self.data = {'game_user': {'user_id': 7}, 'game_state': {'items': {}, 'all_villagers': {}}}
        self.session = dict(id=1, type_id=3, loot_policy=loot.POLICY)
        self.record = dict(time_worked=60, job_activations=3, gold_count=6)
        self.rules = {'items': {str(i): dict(active=True, max_count=0)
                               for pool in loot.POOLS.values() for i, _ in pool}}

    def test_all_original_themed_items_are_reachable_with_one_count_map_entry(self):
        for kind, pool in loot.POOLS.items():
            self.session['type_id'] = kind
            start = 0
            for ident, weight in pool:
                fake = type('Digest', (), {'digest': lambda _: start.to_bytes(8, 'big')})()
                with patch.object(loot.hashlib, 'sha256', return_value=fake):
                    self.assertEqual(loot.reward(self.data, self.session, 1, self.record, self.rules), {str(ident): 1})
                start += weight

    def test_no_idle_early_or_retroactive_awards(self):
        for field, value in (('time_worked', 59), ('job_activations', 0), ('gold_count', 0)):
            record = dict(self.record, **{field: value})
            self.assertEqual(loot.reward(self.data, self.session, 1, record, self.rules), {})
        self.session.pop('loot_policy')
        self.assertEqual(loot.reward(self.data, self.session, 1, self.record, self.rules), {})

    def test_restart_is_deterministic_and_selection_never_mutates_state(self):
        before = copy.deepcopy(self.data)
        first = loot.reward(self.data, self.session, 1, self.record, self.rules)
        self.assertEqual(first, loot.reward(json.loads(json.dumps(self.data)),
            json.loads(json.dumps(self.session)), 1, self.record, self.rules))
        self.assertEqual(self.data, before)
        self.assertEqual(len(first), 1)

    def test_missing_catalog_and_owned_cap_never_create_unknown_or_extra_items(self):
        self.assertEqual(loot.reward(self.data, self.session, 1, self.record, {}), {})
        selected = next(iter(loot.reward(self.data, self.session, 1, self.record, self.rules)))
        self.rules['items'][selected]['max_count'] = 1
        self.data['game_state']['items'][selected] = dict(item_id=int(selected), count=1)
        self.assertEqual(loot.reward(self.data, self.session, 1, self.record, self.rules), {})
