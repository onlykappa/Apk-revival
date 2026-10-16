import copy
import json
import os
import pathlib
import plistlib
import tempfile
import unittest
import zipfile

from apk_revival.meego.engine import birthstones as b


def catalog():
    return {str(ident): {'techtree_id': ident, 'tier': tier, 'active': True,
                        'name': f'Stone {ident}', 'description': 'Synthetic test stone.',
                        'image': f'stone_{ident}.png'}
            for ident, tier in [(1, 1), (2, 1), (3, 2), (4, 3)]}


def village():
    return {'game_user': {'user_id': 10}, 'game_state': {
        'all_villagers': {'1': {'user_id': 10, 'stats': {'birthsigns': [1, 3]}},
                         '2': {'user_id': 10, 'stats': {'birthsigns': [1]}},
                         '3': {'user_id': 20, 'stats': {'birthsigns': [4]}}},
        'unlock_information': {'birthsign_collections': {}, 'unrelated': [9]}}}


class BirthstoneTests(unittest.TestCase):
    def test_original_metadata_loaded_read_only_without_invented_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = pathlib.Path(temporary) / 'test.apk'
            with zipfile.ZipFile(apk, 'w') as archive:
                archive.writestr('assets/TechTree.plist', plistlib.dumps({'version': 2.94, 'techtree': {'birthsigns': catalog()}}))
            before = apk.read_bytes()
            self.assertEqual(b.load_catalog(apk), catalog())
            self.assertEqual(apk.read_bytes(), before)

    def test_patch_retains_other_sections_and_is_strictly_newer_than_original(self):
        packet = {'techtree': {'items': {'99': {'active': True}}}, 'techtree_version': 2.94}
        metadata = catalog()
        b.populate_packet(packet, metadata)
        self.assertEqual(packet['techtree']['birthsigns'], metadata)
        self.assertEqual(packet['techtree']['items'], {'99': {'active': True}})
        self.assertGreater(packet['techtree_version'], 2.94)
        packet['techtree']['birthsigns']['1']['name'] = 'Changed copy'
        self.assertEqual(metadata, catalog())

    def test_newer_existing_version_is_preserved(self):
        packet = {'techtree': {}, 'techtree_version': 3}
        b.populate_packet(packet, catalog())
        self.assertEqual(packet['techtree_version'], 3)

    def test_owned_discoveries_use_tier_keys_numeric_ids_and_exclude_guests(self):
        data = village()
        before_people = copy.deepcopy(data['game_state']['all_villagers'])
        self.assertTrue(b.discover_owned(data, catalog()))
        self.assertEqual(data['game_state']['unlock_information']['birthsign_collections'],
                         {'1': [1], '2': [3], '3': []})
        self.assertEqual(data['game_state']['all_villagers'], before_people)
        self.assertEqual(data['game_state']['unlock_information']['unrelated'], [9])
        self.assertFalse(b.discover_owned(data, catalog()))

    def test_new_child_discovers_stone_once_and_json_restart_retains_it(self):
        data = village()
        b.discover_owned(data, catalog())
        data['game_state']['all_villagers']['4'] = {'user_id': 10, 'stats': {'birthsigns': [4]}}
        self.assertTrue(b.discover_owned(data, catalog()))
        restored = json.loads(json.dumps(data))
        self.assertFalse(b.discover_owned(restored, catalog()))
        self.assertEqual(restored['game_state']['unlock_information']['birthsign_collections']['3'], [4])
        restored['game_state']['all_villagers'].pop('4')
        self.assertFalse(b.discover_owned(restored, catalog()))
        self.assertEqual(restored['game_state']['unlock_information']['birthsign_collections']['3'], [4])

    def test_legacy_string_ids_and_duplicate_discoveries_are_normalized(self):
        data = village()
        collections = data['game_state']['unlock_information']['birthsign_collections']
        collections.update({'1': ['1', 1, 999], '2': [3], '3': [], 'custom': ['keep']})
        self.assertTrue(b.discover_owned(data, catalog()))
        self.assertEqual(collections['1'], [1, 999])
        self.assertEqual(collections['custom'], ['keep'])

    def test_unknown_villager_sign_is_not_fabricated(self):
        data = village()
        data['game_state']['all_villagers']['1']['stats']['birthsigns'] = [999, True, 'bad']
        b.discover_owned(data, catalog())
        self.assertEqual(data['game_state']['unlock_information']['birthsign_collections'],
                         {'1': [1], '2': [], '3': []})

    def test_missing_table_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = pathlib.Path(temporary) / 'test.apk'
            with zipfile.ZipFile(apk, 'w') as archive:
                archive.writestr('assets/TechTree.plist', plistlib.dumps({'techtree': {}}))
            with self.assertRaisesRegex(ValueError, 'metadata is missing'):
                b.load_catalog(apk)


@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'), 'Supply the privately owned original Meego APK')
class OriginalBirthstoneTests(unittest.TestCase):
    def test_all_original_villager_cards_resolve_after_json_wire_roundtrip(self):
        from apk_revival.meego.engine import server
        metadata=b.load_catalog(os.environ['APKR_MEEGO_APK'])
        for key,record in metadata.items():
            person={'villager_id':1,'stats':{'birthsigns':[int(key)]}}
            before=copy.deepcopy(person)
            wire=json.loads(json.dumps(server.native_payload(person)))
            resolved=metadata[wire['stats']['birthsigns'][0]]
            self.assertEqual(resolved,record)
            self.assertTrue(resolved['name'] and resolved['description'] and resolved['image'])
            self.assertEqual(person,before)
        self.assertEqual(metadata['11']['name'],'OWL')

    def test_all_original_records_and_images_including_rabbit_are_present(self):
        apk = pathlib.Path(os.environ['APKR_MEEGO_APK'])
        metadata = b.load_catalog(apk)
        self.assertEqual(len(metadata), 35)
        self.assertEqual(metadata['4']['name'], 'RABBIT')
        self.assertTrue(metadata['4']['description'])
        self.assertEqual(metadata['4']['image'], 'birthstone_rabbit@2x.png')
        with zipfile.ZipFile(apk) as archive:
            names = set(archive.namelist())
            for record in metadata.values():
                self.assertIn('assets/' + record['image'], names)
        self.assertEqual([sum(record['tier'] == tier for record in metadata.values()) for tier in (1, 2, 3)], [20, 10, 5])
        packet = {'techtree': {}, 'techtree_version': 2.94}
        b.populate_packet(packet, metadata)
        self.assertEqual(packet['techtree']['birthsigns'], metadata)
        self.assertGreater(packet['techtree_version'], 2.94)


if __name__ == '__main__':
    unittest.main()
