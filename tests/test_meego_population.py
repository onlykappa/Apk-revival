"""Offline generation tests; no Android or production saves are modified."""
import copy
import json
import os
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import birthstones, community, local_game as g, population as p


def rules():
    stones = {str(i): dict(techtree_id=i, tier=1 if i <= 20 else 2 if i <= 30 else 3,
                           active=True) for i in range(1, 36)}
    items = {}
    for gender in (0, 1):
        for index, slot in enumerate(p.SLOTS):
            for variant in (0, 1, 2):
                ident = 100 + gender * 100 + index * 10 + variant
                items[str(ident)] = dict(techtree_id=ident, active=True, type=1,
                                        collection=slot, gender=gender, given_on_birth=True,
                                        restrictions=[{'layer': 1}])
    return dict(birthsigns=stones, items=items)


def village():
    return {'game_user': {'user_id': 7}, 'game_state': {'all_villagers': {},
            'unlock_information': {'birthsign_collections': {'1': [], '2': [], '3': []}}},
            'unrelated': {'save': 'preserve'}}


def person(ident):
    return g.villager(ident, f'Person {ident}', ident % 2, community.APPEARANCE[ident % 2], 7, 1000)


class PopulationTests(unittest.TestCase):
    def test_same_creation_and_json_restart_reuse_exact_assignment(self):
        data, model, tree = village(), person(1), rules()
        original = copy.deepcopy(model)
        first = p.decorate_new(data, model, tree)
        state = copy.deepcopy(data)
        self.assertEqual(p.decorate_new(data, model, tree), first)
        self.assertEqual(data, state)
        restarted = json.loads(json.dumps(data))
        self.assertEqual(p.decorate_new(restarted, model, tree), first)
        self.assertEqual(restarted, state)
        self.assertEqual(model, original)

    def test_reaches_all_35_one_new_owned_carrier_per_discovery(self):
        data, tree, found = village(), rules(), set()
        for ident in range(1, 36):
            collections = copy.deepcopy(data['game_state']['unlock_information'])
            model = p.decorate_new(data, person(ident), tree)
            self.assertEqual(data['game_state']['unlock_information'], collections)
            stone = model['stats']['birthsigns'][0]
            self.assertNotIn(stone, found)
            self.assertEqual(tree['birthsigns'][str(stone)]['tier'],
                             1 if ident <= 20 else 2 if ident <= 30 else 3)
            found.add(stone)
            data['game_state']['all_villagers'][str(ident)] = model
            birthstones.discover_owned(data, tree['birthsigns'])
            # Old generations may leave; discoveries remain historical.
            del data['game_state']['all_villagers'][str(ident)]
            data = json.loads(json.dumps(data))
        self.assertEqual(found, set(range(1, 36)))
        self.assertEqual(data['unrelated'], {'save': 'preserve'})

    def test_tier_counts_use_original_metadata_not_hardcoded_ids(self):
        tree = rules()
        tree['birthsigns'] = {'40': {'techtree_id': 40, 'active': True, 'tier': 1},
                             '72': {'techtree_id': 72, 'active': True, 'tier': 2},
                             '99': {'techtree_id': 99, 'active': True, 'tier': 3}}
        data = village()
        for ident, expected in enumerate((40, 72, 99), 1):
            model = p.decorate_new(data, person(ident), tree)
            self.assertEqual(model['stats']['birthsigns'], [expected])
            data['game_state']['all_villagers'][str(ident)] = model
        self.assertEqual(data['game_state']['unlock_information']['birthsign_collections'],
                         {'1': [], '2': [], '3': []})

    def test_appearance_has_five_valid_gender_specific_birth_slots(self):
        tree = rules()
        outputs = []
        for ident in range(1, 50):
            model = p.decorate_new(village(), person(ident), tree)
            slots = []
            for item in model['appearance_items']:
                rule = tree['items'][str(item['item_id'])]
                self.assertEqual(rule['gender'], model['gender'])
                self.assertTrue(rule['given_on_birth'])
                self.assertEqual((item['layer'], item['count']), (1, 1))
                slots.append(rule['collection'])
            self.assertEqual(slots, list(p.SLOTS))
            outputs.append(tuple(item['item_id'] for item in model['appearance_items']))
        self.assertGreater(len(set(outputs)), 20)

    def test_parent_input_existing_stats_and_birth_jobs_are_preserved(self):
        data, tree = village(), rules()
        father, mother, child = person(1), person(2), person(3)
        father['stats'].update(strength=40, intelligence=60, charisma=80)
        mother['stats'].update(strength=50, intelligence=70, charisma=90)
        data['game_state']['all_villagers'] = {'1': father, '2': mother}
        child['job'].update(job_id=1, target_id=2)
        child['birthday'] = 1000
        before = copy.deepcopy(data)
        born = p.decorate_new(data, child, tree, parents=(father, mother))
        self.assertEqual(data['game_state'], before['game_state'])
        for stat, center in zip(p.STATS, (45, 65, 85)):
            self.assertLessEqual(abs(born['stats'][stat] - center), 2)
        self.assertEqual(born['job'], child['job'])
        self.assertEqual(born['birthday'], child['birthday'])
        self.assertEqual(born['name'], child['name'])

    def test_existing_or_guest_villagers_cannot_be_rewritten(self):
        for guest in (False, True):
            data, model = village(), person(1)
            if guest:
                model['user_id'] = 8
            else:
                data['game_state']['all_villagers']['legacy-key'] = model
            before = copy.deepcopy(data)
            with self.assertRaises(ValueError):
                p.decorate_new(data, model, rules())
            self.assertEqual(data, before)

    def test_incomplete_old_rules_keep_safe_factory_defaults(self):
        data, model = village(), person(1)
        self.assertEqual(p.decorate_new(data, model, {}), model)
        tree = rules()
        del tree['items']['240']
        del tree['items']['241']
        del tree['items']['242']
        decorated = p.decorate_new(village(), model, tree)
        self.assertEqual(decorated['appearance_items'], model['appearance_items'])

    def test_arrivals_use_variety_without_rewriting_existing_residents(self):
        data, tree = village(), rules()
        data['game_state']['all_villagers']['1'] = person(1)
        original = copy.deepcopy(data['game_state']['all_villagers']['1'])
        community.advance(data, 1000, housing_capacity=5, rules=tree)
        ident = community.advance(data, 1000 + community.INTERVAL_SECONDS,
                                  housing_capacity=5, rules=tree)
        new = data['game_state']['all_villagers'][str(ident)]
        self.assertNotEqual(new['stats']['birthsigns'], [1])
        self.assertEqual(data['game_state']['all_villagers']['1'], original)
        self.assertEqual(len(new['appearance_items']), 5)

    def test_owned_historical_discoveries_and_invalid_items_excluded(self):
        data, tree = village(), rules()
        data['game_state']['unlock_information']['birthsign_collections']['1'] = list(range(1, 21))
        tree['birthsigns']['900'] = dict(techtree_id=900, tier=1, active=False)
        tree['items']['901'] = dict(techtree_id=901, active=True, type=1, gender=1,
                                  given_on_birth=False, collection='mask', restrictions=[{'layer': 1}])
        model = p.decorate_new(data, person(1), tree)
        self.assertEqual(tree['birthsigns'][str(model['stats']['birthsigns'][0])]['tier'], 2)
        self.assertNotIn(901, [i['item_id'] for i in model['appearance_items']])
        self.assertEqual(data['game_state']['unlock_information']['birthsign_collections']['1'],
                         list(range(1, 21)))

    @unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Original APK not supplied')
    def test_original_apk_appearance_and_all_35_stones(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            tree = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        self.assertEqual(len(p._stones(tree)), 35)
        data, seen = village(), set()
        for ident in range(1, 36):
            model = p.decorate_new(data, person(ident), tree)
            seen.update(model['stats']['birthsigns'])
            slots = [tree['items'][str(i['item_id'])]['collection'] for i in model['appearance_items']]
            self.assertEqual(slots, list(p.SLOTS))
            self.assertTrue(all(tree['items'][str(i['item_id'])]['gender'] == model['gender']
                                for i in model['appearance_items']))
            data['game_state']['all_villagers'][str(ident)] = model
            birthstones.discover_owned(data, tree['birthsigns'])
            del data['game_state']['all_villagers'][str(ident)]
        self.assertEqual(seen, set(map(int, tree['birthsigns'])))


if __name__ == '__main__':
    unittest.main()
