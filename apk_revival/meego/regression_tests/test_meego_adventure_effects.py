"""Owned adventure consumables: expiry, provenance and no unearned rewards."""
import copy
import json
import unittest

from apk_revival.meego.engine import effects as e, local_game as g


class AdventureEffectTests(unittest.TestCase):
    def setUp(self):
        self.now = 100000
        self.data = {'game_user': {'user_id': 7}, 'game_state': {
            'points': 12, 'items': {}, 'all_villagers': {
                str(i): g.villager(i, 'Meego', i % 2, [], 7, self.now) for i in (1, 2)}}}
        self.rules = {'items': {str(i): dict(techtree_id=i, type=4, target='self',
                    activate_count=1, duration=3600, bonus_dungeon_reward=bonus)
                    for i, bonus in ((1186, 20), (1511, 50))}}
        for ident in self.rules['items']:
            self.data['game_state']['items'][ident] = dict(item_id=int(ident), count=2,
                                                          cooldown=0, last_update=self.now)

    def test_owned_boost_has_native_effect_and_expires_on_json_restart(self):
        self.assertTrue(e.use_item(self.data, 1, 1186, self.rules, self.now))
        self.assertEqual(self.data['game_state']['items']['1186']['count'], 1)
        self.assertEqual(self.data['game_state']['all_villagers']['1']['effects'],
                         [{'effect_id': 1186, 'expire_date': self.now + 3600}])
        loaded = json.loads(json.dumps(self.data))
        self.assertEqual(e.adventure_bonus(loaded, 1, self.now + 3599), 20)
        self.assertEqual(e.adventure_bonus(loaded, 2, self.now + 3599), 0)
        self.assertEqual(e.adventure_bonus(loaded, 1, self.now + 3600), 0)
        e.advance(loaded, self.now + 3600, self.rules)
        self.assertEqual(loaded['game_state']['all_villagers']['1']['effects'], [])
        self.assertEqual(loaded['game_state']['points'], 12)

    def test_different_boosters_use_maximum_not_additive_stack(self):
        for ident in (1186, 1511):
            e.use_item(self.data, 1, ident, self.rules, self.now)
        self.assertEqual(e.adventure_bonus(self.data, 1, self.now), 50)
        self.assertEqual(self.data['game_state']['points'], 12)

    def test_duplicate_and_social_travel_boosters_reject_without_consuming(self):
        e.use_item(self.data, 1, 1186, self.rules, self.now)
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            e.use_item(self.data, 1, 1186, self.rules, self.now)
        self.assertEqual(self.data, before)
        self.rules['items']['1511'].update(bonus_questing_reward=5)
        with self.assertRaises(g.ActionError):
            e.use_item(self.data, 1, 1511, self.rules, self.now)
        self.assertEqual(self.data, before)

    def test_owned_expiry_never_removes_an_unrelated_native_effect(self):
        person = self.data['game_state']['all_villagers']['1']
        unrelated = dict(effect_id=12345, expire_date=self.now + 9999)
        person['effects'].append(unrelated.copy())
        e.use_item(self.data, 1, 1511, self.rules, self.now)
        e.advance(self.data, self.now + 3600, self.rules)
        self.assertEqual(person['effects'], [unrelated])


if __name__ == '__main__':
    unittest.main()
