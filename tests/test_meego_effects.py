"""Owned item effects use transaction copies, never Android or live saves."""
import copy
import json
import os
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import community, effects as e, local_game as g, skills


def village():
    people = {str(i): g.villager(i, 'Meego', i % 2, community.APPEARANCE[i % 2], 7, 100000)
              for i in (1, 2)}
    return {'game_user': {'user_id': 7}, 'game_state': {'all_villagers': people, 'items': {}},
            'unrelated': ['preserved']}


def rules():
    def item(ident, **extra):
        return dict(techtree_id=ident, type=4, active=True, target='self',
                    activate_count=1, duration=0, lifetime=1, **extra)
    boost = item(398, production_rate_modifier=.267, job_boost_groups=[1])
    boost['duration'] = 3600
    hat = item(371, production_rate_multiplier=1.5, job_boost_groups=[1, 2, 3])
    hat.update(target='village', activate_count=0, duration=180, lifetime=720)
    return {'items': {'398': boost, '371': hat, '830': item(830, add_intelligence=1),
                      '829': item(829, add_lifetime=1), '1512': item(1512, set_age=18),
                      '1502': item(1502, change_hair_colour=1),
                      '1504': item(1504, change_hair=1)},
            'jobs': {'18': {'boost_groups': [1]}, '17': {'boost_groups': [2]},
                     '16': {'boost_groups': [3]}}}


def own(data, ident, count=1, owner=None):
    inventory = (data['game_state']['items'] if owner is None else
                 data['game_state']['all_villagers'][str(owner)]['items'])
    inventory[str(ident)] = dict(item_id=ident, count=count, cooldown=0, last_update=100000)
    return inventory[str(ident)]


class EffectsTests(unittest.TestCase):
    def test_consumable_changes_only_matching_person_job_and_inventory(self):
        data, tree = village(), rules()
        item = own(data, 398)
        self.assertTrue(e.use_item(data, 1, 398, tree, 100000))
        self.assertEqual(item['count'], 0)
        self.assertEqual(e.production_modifiers(data, data['game_state']['all_villagers']['1'], 18,
                                                 100001, tree)['rate_modifier'], .267)
        for ident, job in ((2, 18), (1, 17)):
            self.assertEqual(e.production_modifiers(data, data['game_state']['all_villagers'][str(ident)], job,
                                                     100001, tree)['rate_modifier'], 0)
        self.assertEqual(data['unrelated'], ['preserved'])
        self.assertEqual(data['game_state']['all_villagers']['1']['effects'], [])

    def test_expiry_and_json_restart_exact_boundary_no_permanent_stat_change(self):
        data, tree = village(), rules()
        own(data, 398)
        stats = copy.deepcopy(data['game_state']['all_villagers']['1']['stats'])
        e.use_item(data, 1, 398, tree, 100000)
        data = json.loads(json.dumps(data))
        person = data['game_state']['all_villagers']['1']
        self.assertEqual(e.production_modifiers(data, person, 18, 103599, tree)['rate_modifier'], .267)
        self.assertEqual(e.production_modifiers(data, person, 18, 103600, tree)['rate_modifier'], 0)
        self.assertEqual(e.change_times(data, 99999, 104000), [100000, 103600])
        self.assertTrue(e.advance(data, 103600, tree))
        self.assertFalse(e.advance(data, 103600, tree))
        self.assertEqual(person['stats'], stats)

    def test_reusable_village_hat_owned_cooldown_and_restart(self):
        data, tree = village(), rules()
        own(data, 371, owner=1)
        e.use_item(data, 1, 371, tree, 100000)
        self.assertEqual(data['game_state']['all_villagers']['1']['items']['371']['count'], 1)
        for person in data['game_state']['all_villagers'].values():
            self.assertEqual(e.production_modifiers(data, person, 17, 100179, tree)['rate_multiplier'], 1.5)
            self.assertEqual(e.production_modifiers(data, person, 17, 100180, tree)['rate_multiplier'], 1)
        data = json.loads(json.dumps(data))
        before = copy.deepcopy(data)
        with self.assertRaisesRegex(g.ActionError, 'cooling down'):
            e.use_item(data, 1, 371, tree, 100719)
        self.assertEqual(data, before)
        e.advance(data, 100720, tree)
        self.assertEqual(data['game_state']['all_villagers']['1']['items']['371']['cooldown'], 0)
        self.assertTrue(e.use_item(data, 1, 371, tree, 100720))

    def test_duplicate_active_consumable_rejected_without_second_consumption(self):
        data, tree = village(), rules()
        own(data, 398, count=2)
        e.use_item(data, 1, 398, tree, 100000)
        before = copy.deepcopy(data)
        with self.assertRaisesRegex(g.ActionError, 'already active'):
            e.use_item(data, 1, 398, tree, 100001)
        self.assertEqual(data, before)

    def test_equipped_inventory_precedes_village_inventory(self):
        data, tree = village(), rules()
        own(data, 398, count=2)
        own(data, 398, owner=1)
        e.use_item(data, 1, 398, tree, 100000)
        self.assertEqual(data['game_state']['items']['398']['count'], 2)
        self.assertEqual(data['game_state']['all_villagers']['1']['items']['398']['count'], 0)

    def test_missing_ownership_dead_and_guest_rejected_without_mutation(self):
        for case in ('missing', 'dead', 'guest'):
            data, tree = village(), rules()
            if case != 'missing':
                own(data, 398)
            if case == 'dead':
                data['game_state']['all_villagers']['1']['job']['job_id'] = 6
            if case == 'guest':
                data['game_state']['all_villagers']['1']['user_id'] = 9
            before = copy.deepcopy(data)
            with self.assertRaises(g.ActionError):
                e.use_item(data, 1, 398, tree, 100000)
            self.assertEqual(data, before)

    def test_permanent_self_stat_still_delegates_original_handler(self):
        data, tree = village(), rules()
        own(data, 830)
        before = copy.deepcopy(data)
        self.assertFalse(e.use_item(data, 1, 830, tree, 100000))
        self.assertEqual(data, before)
        skills.use_item(data, 1, 830, tree, 100000)
        self.assertEqual(data['game_state']['all_villagers']['1']['stats']['intelligence'], 11)
        self.assertEqual(data['game_state']['items']['830']['count'], 0)

    def test_age_effect_preserves_total_lifespan_and_other_earned_fields(self):
        data, tree = village(), rules()
        own(data, 829)
        person = data['game_state']['all_villagers']['1']
        before = copy.deepcopy(person)
        e.use_item(data, 1, 829, tree, 100000, hours_per_age=2)
        self.assertEqual(person['birthday'] - before['birthday'], 7200)
        self.assertEqual(person['deathday'] - before['deathday'], 7200)
        for field in ('stats', 'appearance_items', 'job'):
            self.assertEqual(person[field], before[field])

    def test_set_age_and_younger_than_birth_clamp(self):
        data, tree = village(), rules()
        own(data, 1512)
        person = data['game_state']['all_villagers']['1']
        e.use_item(data, 1, 1512, tree, 100000)
        self.assertEqual(person['birthday'], 100000 - 18 * 3600)
        tree['items']['829']['add_lifetime'] = 1000
        own(data, 829)
        e.use_item(data, 1, 829, tree, 100000)
        self.assertEqual(person['birthday'], 100000)

    def test_mojo_receipt_and_mixed_signed_stats_use_existing_cap(self):
        data, tree = village(), rules()
        tree['items']['1594'] = dict(techtree_id=1594, type=4, target='self', activate_count=1,
                                    duration=0, lifetime=1, affluence=200, add_charisma=3)
        own(data, 1594)
        data['game_state']['all_villagers']['1']['stats']['charisma'] = 1798
        self.assertTrue(e.use_item(data, 1, 1594, tree, 100000))
        self.assertEqual(data['local_affluence_delta'], 200)
        self.assertEqual(data['game_state']['all_villagers']['1']['stats']['charisma'], 1799)
        self.assertEqual(data['game_state']['items']['1594']['count'], 0)

    def test_unknown_scripts_infections_and_quest_effects_not_consumed(self):
        for extra in ({'script': 'JFSoccerBall.lua', 'target': 'village'},
                      {'target': 'subset'}, {'bonus_dungeon_reward': 20},
                      {'bonus_questing_reward': 7}):
            data, tree = village(), rules()
            tree['items']['398'].update(extra)
            own(data, 398)
            before = copy.deepcopy(data)
            with self.assertRaises(g.ActionError):
                e.use_item(data, 1, 398, tree, 100000)
            self.assertEqual(data, before)

    def test_invalid_numeric_metadata_rejected_atomically(self):
        for field, value in (('duration', float('nan')), ('production_rate_multiplier', 0),
                             ('production_time_modifier', float('inf'))):
            data, tree = village(), rules()
            tree['items']['398'][field] = value
            own(data, 398)
            before = copy.deepcopy(data)
            with self.assertRaises(g.ActionError):
                e.use_item(data, 1, 398, tree, 100000)
            self.assertEqual(data, before)

    def test_explicit_job_or_group_matches_and_modifiers_compose_once(self):
        data, tree = village(), rules()
        tree['items']['398'].update(production_time_modifier=-.25, production_time_multiplier=.9)
        own(data, 398)
        own(data, 371)
        e.use_item(data, 1, 398, tree, 100000)
        e.use_item(data, 1, 371, tree, 100000)
        person = data['game_state']['all_villagers']['1']
        self.assertEqual(e.production_modifiers(data, person, 18, 100001, tree),
                         dict(rate_modifier=.267, rate_multiplier=1.5,
                              time_modifier=-.25, time_multiplier=.9))
        tree['items']['398'].update(job_ids=[17], job_boost_groups=[])
        self.assertEqual(e.production_modifiers(data, person, 17, 100001, tree)['rate_modifier'], .267)
        self.assertEqual(e.production_modifiers(data, person, 18, 100001, tree)['rate_modifier'], 0)

    @unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Original APK not supplied')
    def test_original_hair_potions_hats_and_commercial_consumable(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            tree = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        for gender, ident in ((1, 1), (0, 2)):
            for potion in (1502, 1504):
                data = village()
                person = data['game_state']['all_villagers'][str(ident)]
                original_hair = tree['items'][str(person['appearance_items'][-1]['item_id'])]
                own(data, potion)
                e.use_item(data, ident, potion, tree, 100000)
                new = tree['items'][str(person['appearance_items'][-1]['item_id'])]
                self.assertEqual(new['gender'], gender)
                self.assertEqual(new['collection'], 'hair')
                self.assertEqual(new.get('base_id') == original_hair.get('base_id'), potion == 1502)
                self.assertTrue(new['given_on_birth'])
        for hat_id, multiplier, cooldown in ((371, 1.5, 720), (596, 2, 720),
                                             (374, 2.5, 2700), (376, 3, 2700)):
            data = village()
            own(data, hat_id)
            self.assertTrue(e.use_item(data, 1, hat_id, tree, 100000))
            self.assertEqual(data['game_state']['items'][str(hat_id)]['cooldown'], cooldown)
            self.assertEqual(e.production_modifiers(data, data['game_state']['all_villagers']['2'], 18,
                                                     100001, tree)['rate_multiplier'], multiplier)
        data = village()
        own(data, 398)
        self.assertTrue(e.use_item(data, 1, 398, tree, 100000))
        self.assertEqual(e.production_modifiers(data, data['game_state']['all_villagers']['1'], 18,
                                                 100001, tree)['rate_modifier'], .267)


if __name__ == '__main__':
    unittest.main()
