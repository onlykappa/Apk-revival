import copy
import json
import os
import pathlib
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import catalog, local_game as g


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000000
        self.gs = {'points': 10, 'achievements': {'102': {'level': 4}},
                   'resources': {str(i): {'count': 1000, 'last_update': 1} for i in range(1, 6)},
                   'items': {}, 'all_villagers': {},
                   'unlock_information': {'unlocked_item_cursors': []}}
        self.rules = {'items': {
            '10': {'active': True, 'items_store_purchasable': True, 'research_points': 30,
                   'research_temple_level': 2, 'points_cost': 2, 'max_count': 0,
                   'unlock_achievement_id': 102, 'unlock_achievement_level': 2,
                   'conversion_map': {'1': {'output_count': 1, 'input_counter_units': [
                       {'counter_unit_id': 359, 'count': 5}, {'counter_unit_id': 360, 'count': 10}]}}},
            '11': {'active': True, 'items_store_purchasable': True, 'research_points': 60,
                   'research_temple_level': 4, 'research_required_item_id': 10, 'points_cost': 3,
                   'conversion_map': {'1': {'output_count': 1, 'input_counter_units': [
                       {'counter_unit_id': 359, 'count': 20}, {'counter_unit_id': 10, 'count': 1}]}}},
            '12': {'active': True, 'items_store_purchasable': True, 'points_cost': 0},
        }}

    def test_research_then_craft_debits_original_recipe_not_zero_price(self):
        catalog.research_item(self.gs, 10, self.rules, self.now)
        catalog.purchase_item(self.gs, 10, 2, False, self.rules, self.now + 1)
        self.assertEqual(self.gs['resources']['4']['count'], 970)
        self.assertEqual(self.gs['resources']['1']['count'], 990)
        self.assertEqual(self.gs['resources']['2']['count'], 980)
        self.assertEqual(self.gs['items']['10']['count'], 2)
        self.assertEqual(self.gs['points'], 10)
        self.assertEqual(self.gs['unlock_information']['unlocked_item_cursors'], ['10'])

    def test_skull_purchase_bypasses_research_without_unlocking_recipe(self):
        catalog.purchase_item(self.gs, 10, 1, True, self.rules, self.now)
        self.assertEqual(self.gs['points'], 8)
        self.assertEqual(self.gs['resources']['1']['count'], 1000)
        self.assertEqual(catalog.researched_items(self.gs, self.rules), set())
        before = copy.deepcopy(self.gs)
        with self.assertRaisesRegex(g.ActionError, 'Research this item'):
            catalog.purchase_item(self.gs, 10, 1, False, self.rules, self.now)
        self.assertEqual(self.gs, before)

    def test_predecessor_research_is_required_and_research_retry_is_free(self):
        before = copy.deepcopy(self.gs)
        with self.assertRaisesRegex(g.ActionError, 'previous item'):
            catalog.research_item(self.gs, 11, self.rules, self.now)
        self.assertEqual(self.gs, before)
        catalog.research_item(self.gs, 10, self.rules, self.now)
        catalog.research_item(self.gs, 11, self.rules, self.now)
        after = copy.deepcopy(self.gs)
        catalog.research_item(self.gs, 11, self.rules, self.now + 1)
        self.assertEqual(self.gs, after)
        self.assertEqual(self.gs['resources']['4']['count'], 910)

    def test_upgrade_recipe_consumes_unequipped_previous_tool_once(self):
        self.gs['unlock_information']['unlocked_item_cursors'] = ['11']
        self.gs['items']['10'] = {'count': 1, 'last_update': 1}
        catalog.purchase_item(self.gs, 11, 1, False, self.rules, self.now)
        self.assertEqual(self.gs['items']['10']['count'], 0)
        self.assertEqual(self.gs['items']['11']['count'], 1)
        self.assertEqual(self.gs['resources']['1']['count'], 980)
        before = copy.deepcopy(self.gs)
        with self.assertRaisesRegex(g.ActionError, 'earlier tool'):
            catalog.purchase_item(self.gs, 11, 1, False, self.rules, self.now)
        self.assertEqual(self.gs, before)

    def test_equipped_previous_tool_is_not_silently_removed(self):
        self.gs['unlock_information']['unlocked_item_cursors'] = ['11']
        self.gs['all_villagers']['1'] = {'items': {'10': {'count': 1}}}
        before = copy.deepcopy(self.gs)
        with self.assertRaisesRegex(g.ActionError, 'Unequip'):
            catalog.purchase_item(self.gs, 11, 1, False, self.rules, self.now)
        self.assertEqual(self.gs, before)

    def test_limit_counts_equipped_inventory(self):
        self.rules['items']['10']['max_count'] = 1
        self.gs['all_villagers']['1'] = {'items': {'10': {'count': 1}}}
        before = copy.deepcopy(self.gs)
        with self.assertRaisesRegex(g.ActionError, 'Maximum item count'):
            catalog.purchase_item(self.gs, 10, 1, True, self.rules, self.now)
        self.assertEqual(self.gs, before)

    def test_migrate_singleton_pair_cursors_preserves_research_after_restart(self):
        self.gs['unlock_information']['unlocked_item_cursors'] = [[11, 11], 10, '10', '999']
        self.assertTrue(catalog.normalize_research_cursors(self.gs, self.rules))
        self.gs = json.loads(json.dumps(self.gs))
        self.assertEqual(self.gs['unlock_information']['unlocked_item_cursors'], ['11', '10', '999'])
        self.assertEqual(catalog.researched_items(self.gs, self.rules), {'11', '10', '999'})
        self.assertFalse(catalog.normalize_research_cursors(self.gs, self.rules))
        catalog.purchase_item(self.gs, 10, 1, False, self.rules, self.now)

    def test_zero_prices_and_missing_recipes_do_not_grant_free_items(self):
        for use_points in (False, True):
            before = copy.deepcopy(self.gs)
            with self.assertRaises(g.ActionError):
                catalog.purchase_item(self.gs, 12, 1, use_points, self.rules, self.now)
            self.assertEqual(self.gs, before)

    def test_insufficient_inputs_and_locked_temple_are_atomic(self):
        self.gs['unlock_information']['unlocked_item_cursors'] = ['10']
        for resource, amount in [('2', 0), ('4', 0)]:
            self.gs['resources'][resource]['count'] = amount
            before = copy.deepcopy(self.gs)
            with self.assertRaises(g.ActionError):
                if resource == '4':
                    catalog.research_item(self.gs, 11, self.rules, self.now)
                else:
                    catalog.purchase_item(self.gs, 10, 1, False, self.rules, self.now)
            self.assertEqual(self.gs, before)
        self.gs['achievements']['102']['level'] = 1
        before = copy.deepcopy(self.gs)
        with self.assertRaises(g.ActionError):
            catalog.purchase_item(self.gs, 10, 1, True, self.rules, self.now)
        self.assertEqual(self.gs, before)

    def test_bad_recipe_fails_before_any_inventory_change(self):
        self.gs['unlock_information']['unlocked_item_cursors'] = ['10']
        self.rules['items']['10']['conversion_map']['1']['input_counter_units'].append(
            {'counter_unit_id': 360, 'count': -10})
        before = copy.deepcopy(self.gs)
        with self.assertRaises(g.ActionError):
            catalog.purchase_item(self.gs, 10, 1, False, self.rules, self.now)
        self.assertEqual(self.gs, before)


@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'), 'Supply the privately owned original Meego APK')
class BundledCatalogTests(unittest.TestCase):
    def test_all_original_shop_prices_and_recipes(self):
        with zipfile.ZipFile(pathlib.Path(os.environ['APKR_MEEGO_APK'])) as archive:
            rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        self.assertEqual(len(rules['items']), 327)
        self.assertEqual(len(rules['buildings']), 42)
        self.assertEqual(len(rules['jobs']), 56)
        self.assertEqual(len(rules['points_store']), 135)
        purchasable = {key: rule for key, rule in rules['items'].items() if rule.get('items_store_purchasable')}
        self.assertEqual(len(purchasable), 50)
        successful, unsupported = set(), set()
        for ident, rule in purchasable.items():
            with self.subTest(item=ident):
                gs = {'points': 10000, 'achievements': {'102': {'level': 12}},
                      'resources': {str(i): {'count': 100000000} for i in range(1, 6)},
                      'items': {key: {'count': 1000} for key in rules['items'] if key != ident},
                      'all_villagers': {},
                      'unlock_information': {'unlocked_item_cursors': list(rules['items'])}}
                recipe = rule.get('conversion_map', {}).get('1')
                if recipe:
                    catalog.purchase_item(gs, ident, 1, False, rules, 1000000)
                    self.assertEqual(gs['items'][ident]['count'], 1)
                    for ingredient in recipe['input_counter_units']:
                        resource = g.RESOURCE_IDS.get(ingredient['counter_unit_id'])
                        actual = gs['resources'][str(resource)]['count'] if resource else gs['items'][str(ingredient['counter_unit_id'])]['count']
                        self.assertEqual(actual, (100000000 if resource else 1000) - ingredient['count'])
                    successful.add(ident)
                elif rule.get('points_cost', 0) > 0:
                    catalog.purchase_item(gs, ident, 1, True, rules, 1000000)
                    self.assertEqual(gs['points'], 10000 - rule['points_cost'])
                    successful.add(ident)
                elif ident == '371':
                    self.assertEqual((rule['cost'], rule['points_cost']), (0, 0))
                    resources = copy.deepcopy(gs['resources'])
                    catalog.purchase_item(gs, ident, 1, False, rules, 1000000)
                    self.assertEqual(gs['items'][ident]['count'], 1)
                    self.assertEqual(gs['resources'], resources)
                    self.assertEqual(gs['points'], 10000)
                    successful.add(ident)
                else:
                    with self.assertRaises(g.ActionError):
                        catalog.purchase_item(gs, ident, 1, False, rules, 1000000)
                    unsupported.add(ident)
        self.assertEqual(len(successful), 50)
        self.assertEqual(unsupported, set())


if __name__ == '__main__':
    unittest.main()
