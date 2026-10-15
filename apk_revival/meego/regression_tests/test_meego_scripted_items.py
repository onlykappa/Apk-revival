import copy
import os
import plistlib
import unittest
import zipfile
from apk_revival.meego.engine import local_game as g, scripted_items as s


class ScriptedGiftTests(unittest.TestCase):
    def setUp(self):
        self.rules = {'items': {str(ident): dict(type=8, gift_type=3, script=script)
                               for ident, script in s.COSMETIC_GIFTS.items()}}
        self.rules['items']['994'] = dict(type=8, gift_type=2, minigame_type=2, script='JFMosquito.lua')
        self.rules['items']['995'] = dict(type=8, gift_type=2, minigame_type=3, script='JFHugBug.lua')
        self.data = {'game_state': {'gifts': {}, 'items': {}, 'points': 7,
                     'all_villagers': {'1': g.villager(1, 'Test', 1, [], 3, 10000)}}}

    def gift(self, kind, gift_type=3):
        self.data['game_state']['gifts']['9'] = dict(gift_id=9, gift_item_id=kind,
            gift_type=gift_type, gift_count=1, from_user_id=3, from_username='Local')

    def test_three_client_only_gifts_open_existing_boxes_without_gameplay_mutation(self):
        for kind in s.COSMETIC_GIFTS:
            self.gift(kind)
            before = copy.deepcopy(self.data)
            new, response = s.open_gift(self.data, {'gift_id': ['9'], 'villager_ids': ['[]']}, self.rules, 10000)
            expected = copy.deepcopy(before)
            expected['game_state']['gifts'] = {}
            self.assertEqual(new, expected)
            self.assertEqual(response, {'game_state': new['game_state']})
            self.assertEqual(self.data, before)
            with self.assertRaises(g.ActionError):
                s.open_gift(new, {'gift_id': ['9']}, self.rules, 10001)

    def test_bug_sessions_are_not_faked_or_consumed(self):
        for kind in s.BUG_GIFTS:
            self.gift(kind, 2)
            before = copy.deepcopy(self.data)
            with self.assertRaisesRegex(g.ActionError, 'not consumed'):
                s.open_gift(self.data, {'gift_id': ['9']}, self.rules, 10000)
            self.assertEqual(self.data, before)

    def test_inventory_is_not_fabricated_into_incoming_gift(self):
        self.data['game_state']['items']['997'] = dict(item_id=997, count=1)
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            s.open_gift(self.data, {'gift_id': ['997']}, self.rules, 10000)
        self.assertEqual(self.data, before)

    def test_rejects_unknown_stack_mismatch_or_villager_target_without_consumption(self):
        for change, params in (({'gift_count': 2}, {}), ({'gift_count': True}, {}),
                              ({'gift_type': 2}, {}), ({'gift_item_id': 999}, {}),
                              ({'gift_id': 8}, {}), ({}, {'villager_ids': ['[1]']}),
                              ({}, {'villager_ids': ['invalid']})):
            self.gift(997)
            self.data['game_state']['gifts']['9'].update(change)
            before = copy.deepcopy(self.data)
            with self.assertRaises(g.ActionError):
                s.open_gift(self.data, {'gift_id': ['9'], **params}, self.rules, 10000)
            self.assertEqual(self.data, before)


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
class OriginalScriptedGiftTests(unittest.TestCase):
    def test_original_classification_and_client_prank_restoration(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
            for ident, script in s.COSMETIC_GIFTS.items():
                original = rules['items'][str(ident)]
                self.assertEqual((original['type'], original['gift_type'], original['script']), (8, 3, script))
            for ident, kind in s.BUG_GIFTS.items():
                self.assertEqual(rules['items'][str(ident)]['minigame_type'], kind)
            prank = archive.read('assets/scripts/pranks/JFTombstoneGift.lua').decode()
            self.assertIn('"undoPrank"', prank)
            self.assertIn('self:unkillVillagers()', prank)
            self.assertNotIn('setDeathday', prank)
