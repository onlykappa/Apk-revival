import copy
import json
import os
from pathlib import Path
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import progression as p


def achievement(descriptions):
    return {'active': True, 'max_level': len(descriptions),
            'level_client_data': {str(index): {'detail_description': text}
                                  for index, text in enumerate(descriptions, 1)}}


def rules():
    return {
        'achievements': {
            '105': achievement(['2 Babies', '40 Babies']),
            '107': achievement(['Played 3 Days', 'Played 10 Days']),
            '338': achievement(['Played 1 Year', 'Played 2 Years']),
            '160': achievement(['2 Common Birthstones', '3 Common Birthstones']),
            '173': achievement(['1 Uncommon Birthstone']),
            '174': achievement(['1 Rare Birthstone']),
            '128': {'active': True, 'max_level': 2},
            '104': achievement(['1 Tourists']),
            '161': achievement(['1 Tribe Members'])},
        'birthsigns': {'1': {'tier': 1}, '2': {'tier': 1}, '3': {'tier': 1},
                      '4': {'tier': 2}, '5': {'tier': 3}},
        'buildings': {
            '1': {'state_data': {
                '1': {'temple_level': 1, 'affluence': 0},
                '10': {'temple_level': 1, 'affluence': 0, 'buildable': True},
                '11': {'temple_level': 2, 'affluence': 1970},
                '21': {'temple_level': 3, 'affluence': 3940}}},
            '10': {'state_data': {'1': {'transition_achievements': {
                '9': {'achievement_id': 128, 'achievement_level': 1},
                '18': {'achievement_id': 128, 'achievement_level': 2}},
                'client_data': {'completes_tutorial_tasks': ['farm_built']}}}}},
        'client_data': {'1': {
            'tutorial_task_farm_built': {'task_id': 31, 'is_one_time_task': True},
            'tutorial_task_harvest_food': {'task_id': 2, 'is_one_time_task': True}}}}


def village():
    return {'created_at': 1_000_000, 'game_user': {'village_level': 1},
            'game_state': {'achievements': {}, 'points': 7,
                           'resources': {'1': {'count': 4}}, 'items': {'42': {'count': 2}},
                           'village_information': {'affluence': 542},
                           'unlock_information': {'birthsign_collections': {}},
                           'buildings': {}}, 'unrelated': {'keep': True}}


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        self.data = village()
        self.rules = rules()
        self.now = self.data['created_at']

    def test_production_unlocks_exactly_at_nine_and_eighteen_accepted_cycles(self):
        for index in range(8):
            self.assertTrue(p.record_production_cycle(self.data, 10, 50, f'cycle-{index}', self.now, self.rules))
        self.assertNotIn('128', self.data['game_state']['achievements'])
        self.assertTrue(p.record_production_cycle(self.data, 10, 50, 'cycle-8', self.now, self.rules))
        self.assertEqual(self.data['game_state']['achievements']['128']['level'], 1)
        after = copy.deepcopy(self.data)
        self.assertFalse(p.record_production_cycle(self.data, 10, 50, 'cycle-8', self.now + 1, self.rules))
        self.assertEqual(self.data, after)
        self.data = json.loads(json.dumps(self.data))
        for index in range(9, 18):
            p.record_production_cycle(self.data, 10, 50, f'cycle-{index}', self.now, self.rules)
        self.assertEqual(self.data['game_state']['achievements']['128']['level'], 2)
        self.assertFalse(p.record_production_cycle(self.data, 10, 50, 'later-cycle', self.now, self.rules))
        self.assertEqual(len(self.data[p.STATE_KEY]['production']['10:50']['events']), 18)
        self.assertEqual(self.data['game_state']['points'], 7)

    def test_production_use_is_per_instance_and_unrelated_building_not_counted(self):
        for index in range(8):
            p.record_production_cycle(self.data, 10, 50, f'cycle-{index}', self.now, self.rules)
        p.record_production_cycle(self.data, 10, 51, 'new-cycle', self.now, self.rules)
        self.assertNotIn('128', self.data['game_state']['achievements'])
        before = copy.deepcopy(self.data)
        self.assertFalse(p.record_production_cycle(self.data, 5, 50, 'cycle', self.now, self.rules))
        self.assertEqual(self.data, before)

    def test_birth_token_history_survives_retry_cache_eviction_and_restart(self):
        self.data['completed_births'] = {'first': {'baby_id': 3}}
        p.synchronize(self.data, self.now, self.rules)
        self.assertNotIn('105', self.data['game_state']['achievements'])
        self.data['completed_births'] = {'second': {'baby_id': 4}}
        p.synchronize(self.data, self.now, self.rules)
        self.assertEqual(self.data['game_state']['achievements']['105']['level'], 1)
        after = json.loads(json.dumps(self.data))
        self.assertFalse(p.synchronize(after, self.now, self.rules))
        self.assertEqual(after, self.data)
        self.assertEqual(set(after[p.STATE_KEY]['birth_events']), {'first', 'second'})
        self.assertEqual(after['game_state']['points'], 7)

    def test_legacy_achievement_levels_and_unrelated_fields_never_removed(self):
        self.data['game_state']['achievements'] = {
            '105': {'achievement_id': 105, 'level': 5, 'last_updated': 5, 'custom': 'preserved'},
            '999': {'level': 3}}
        before = copy.deepcopy(self.data['game_state']['achievements'])
        self.data['completed_births'] = {'first': {}, 'second': {}}
        p.synchronize(self.data, self.now, self.rules)
        self.assertEqual(self.data['game_state']['achievements'], before)
        self.assertEqual(self.data['unrelated'], {'keep': True})

    def test_only_earned_unique_known_birthstones_unlock_collection_badges(self):
        self.data['game_state']['unlock_information']['birthsign_collections'] = {
            '1': [1, '1', 2, 999, True], '2': [4], '3': []}
        p.synchronize(self.data, self.now, self.rules)
        earned = self.data['game_state']['achievements']
        self.assertEqual(earned['160']['level'], 1)
        self.assertEqual(earned['173']['level'], 1)
        self.assertNotIn('174', earned)
        self.assertNotIn('104', earned)
        self.assertNotIn('161', earned)
        self.assertEqual(self.data['game_state']['points'], 7)
        self.assertEqual(self.data['game_state']['items'], {'42': {'count': 2}})

    def test_elapsed_age_policy_uses_original_day_year_thresholds_and_no_xp(self):
        p.synchronize(self.data, self.now + 3 * 86400 - 1, self.rules)
        self.assertNotIn('107', self.data['game_state']['achievements'])
        p.synchronize(self.data, self.now + 3 * 86400, self.rules)
        self.assertEqual(self.data['game_state']['achievements']['107']['level'], 1)
        p.synchronize(self.data, self.now + 365 * 86400, self.rules)
        self.assertEqual(self.data['game_state']['achievements']['338']['level'], 1)
        self.assertNotIn('xp', self.data['game_state'])
        self.assertEqual(self.data['game_state']['points'], 7)

    def test_affluence_meter_and_village_number_follow_same_milestones(self):
        p.synchronize(self.data, self.now, self.rules)
        info = self.data['game_state']['village_information']
        self.assertEqual((info['current_level_affluence'], info['next_level_affluence']), (0, 1970))
        info['affluence'] = 2000
        p.synchronize(self.data, self.now, self.rules)
        self.assertEqual((info['current_level_affluence'], info['next_level_affluence']), (1970, 3940))
        self.assertEqual(self.data['game_user']['village_level'], 2)
        self.assertEqual(info['village_level'], 2)
        self.assertEqual(p.affluence_bounds(3940, self.rules), (3940, 5910))
        self.assertIsNone(p.affluence_bounds(4000, {}))

    def test_tutorial_original_name_and_numeric_id_are_idempotent_without_payout(self):
        self.assertTrue(p.complete_tutorial_task(self.data, 'harvest_food', self.rules))
        self.assertFalse(p.complete_tutorial_task(self.data, '2', self.rules))
        self.assertFalse(p.complete_tutorial_task(self.data, 'tutorial_task_harvest_food', self.rules))
        before = copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError, 'original game rules'):
            p.complete_tutorial_task(self.data, 'give_me_skulls', self.rules)
        self.assertEqual(self.data, before)
        self.data['game_state']['buildings']['50'] = {'building_type': 10, 'state': 1}
        p.synchronize(self.data, self.now, self.rules)
        self.assertIn('farm_built', self.data['local_tutorial_tasks'])
        self.assertEqual(self.data['game_state']['points'], 7)

    def test_empty_rules_do_not_change_saved_data(self):
        before = copy.deepcopy(self.data)
        self.assertFalse(p.synchronize(self.data, self.now, {}))
        self.assertEqual(self.data, before)

    def test_first_counter_migration_reports_change_even_without_new_badges(self):
        self.data['game_state']['village_information'].update(
            current_level_affluence=0, next_level_affluence=1970)
        self.assertTrue(p.synchronize(self.data, self.now, self.rules))
        self.assertFalse(p.synchronize(self.data, self.now, self.rules))


@unittest.skipUnless(os.getenv('APKR_MEEGO_APK'), 'Supply the privately owned original Meego APK')
class OriginalRulesProgressionTests(unittest.TestCase):
    def setUp(self):
        with zipfile.ZipFile(Path(os.environ['APKR_MEEGO_APK'])) as archive:
            self.rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']

    def test_original_production_unlocks_all_three_paths_at_original_thresholds(self):
        data = village()
        for kind, ident in [(10, '128'), (13, '131'), (16, '130')]:
            for index in range(18):
                p.record_production_cycle(data, kind, kind + 100, str(index), 1000000, self.rules)
                if index == 8:
                    self.assertEqual(data['game_state']['achievements'][ident]['level'], 1)
            self.assertEqual(data['game_state']['achievements'][ident]['level'], 2)
        self.assertEqual(data['game_state']['points'], 7)

    def test_original_birth_and_collection_thresholds_have_no_unknown_reward_grants(self):
        data = village()
        data['completed_births'] = {'first': {}, 'second': {}}
        collections = {str(tier): [int(key) for key, record in self.rules['birthsigns'].items()
                                  if record['tier'] == tier] for tier in (1, 2, 3)}
        data['game_state']['unlock_information']['birthsign_collections'] = collections
        p.synchronize(data, data['created_at'] + 90 * 86400, self.rules)
        self.assertEqual(data['game_state']['achievements']['105']['level'], 1)
        self.assertEqual(data['game_state']['achievements']['107']['level'], 5)
        for ident in ('160', '173', '174'):
            self.assertEqual(data['game_state']['achievements'][ident]['level'], 2)
        self.assertEqual(data['game_state']['points'], 7)
        self.assertEqual(p.affluence_bounds(542, self.rules), (0, 1970))
        self.assertEqual(len(self.rules['achievements']), 23)
        self.assertFalse(any('reward' in key for record in self.rules['achievements'].values()
                             for key in record))
