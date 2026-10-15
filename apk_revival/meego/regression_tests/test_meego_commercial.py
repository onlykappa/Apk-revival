"""Commercial rewards use synthetic villages; original APK is read-only."""
import copy
import json
import os
import plistlib
import unittest
import zipfile
from unittest.mock import patch

from apk_revival.meego.engine import commercial as c, local_game as g, production as p


def params(**values):
    return {key: [str(value)] for key, value in values.items()}


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.now = 10000
        self.rules = {'buildings': {'11': {'state_data': {
            '1': {'valid_transitions': [11]},
            '11': {'active_job': 21, 'default_length': 3600,
                   'default_interval': 1, 'counter_unit_cost': {'361': 490}}}}},
            'jobs': {'21': {'random_drop': {'0': {'398': {'chance': 60,
                'count_contribution': {'constant': 1}}},
                '12': {'500': {'chance': 100, 'count_contribution': {'constant': 1}}}}}},
            'items': {'398': {}, '500': {}}}
        self.data = {'game_user': {'user_id': 3}, 'game_state': {
            'resources': {'3': {'count': 5000}}, 'points': 0,
            'achievements': {}, 'items': {},
            'buildings': {'7': g.building(7, 11, 1, 300, self.now)},
            'all_villagers': {'1': g.villager(1, 'Test', 1, [], 3, self.now)}}}
        p.activate_for_job(self.data['game_state'], 21, 7, {}, self.rules, self.now)
        self.source = self.data['game_state']['buildings']['7']
        self.person = self.data['game_state']['all_villagers']['1']
        self.person['job'].update(job_id=21, source_id=7, job_start_date=self.now)

    def settle(self, data=None, elapsed=3600):
        data = self.data if data is None else data
        with patch.object(c, '_roll', return_value=0):
            c.advance(data, self.now+3600, elapsed, self.rules)

    def test_only_full_paid_work_stages_item_until_explicit_collection(self):
        self.settle()
        self.assertEqual(self.data['game_state']['items'], {})
        self.assertEqual(self.source['items']['398']['count'], 1)
        self.assertEqual(self.data['game_state']['unlock_information']['job_attempts']['21'], 1)
        p.advance_cycles(self.data, self.now+3600, 3600, self.rules)
        self.assertEqual(self.source['state'], 1)
        new = c.collect(self.data, params(building_type_id=11, location=300), self.rules, self.now+3600)
        self.assertEqual(new['game_state']['items']['398']['count'], 1)
        self.assertEqual(new['game_state']['buildings']['7']['items'], {})
        retry = c.collect(new, params(building_type_id=11, location=300), self.rules, self.now+3600)
        self.assertEqual(new, retry)
        self.assertEqual(self.data['game_state']['items'], {})

    def test_same_tick_and_json_restart_do_not_reroll(self):
        self.settle()
        before = copy.deepcopy(self.data)
        self.settle()
        self.assertEqual(self.data, before)
        restored = json.loads(json.dumps(self.data))
        with patch.object(c, '_roll', side_effect=AssertionError('reroll')):
            c.advance(restored, self.now+8000, 4400, self.rules)
        self.assertEqual(restored, before)

    def test_no_worker_partial_worker_unpaid_and_legacy_cycles_do_not_award(self):
        for mode in ('missing', 'partial', 'unpaid', 'legacy'):
            with self.subTest(mode=mode):
                data = copy.deepcopy(self.data)
                source = data['game_state']['buildings']['7']
                job = data['game_state']['all_villagers']['1']['job']
                if mode == 'missing':
                    job['job_id'] = 0
                elif mode == 'partial':
                    job['job_start_date'] += 1
                elif mode == 'unpaid':
                    source.pop('local_production_cycle')
                else:
                    source.pop('local_production_policy')
                self.settle(data)
                self.assertEqual(source['items'], {})
                self.assertEqual(data['game_state'].get('unlock_information', {}), {})

    def test_poll_segmentation_and_json_restart_match_single_step(self):
        for second in range(60, 3601, 60):
            c.advance(self.data, self.now+second, 60, self.rules)
            self.data = json.loads(json.dumps(self.data))
        self.assertEqual(self.data['game_state']['buildings']['7'][c.STATE]['worked'], 3600)
        self.assertEqual(self.data['game_state']['unlock_information']['job_attempts']['21'], 1)

    def test_second_paid_cycle_preserves_uncollected_items(self):
        self.settle()
        p.advance_cycles(self.data, self.now+3600, 3600, self.rules)
        self.now += 3600
        p.activate_for_job(self.data['game_state'], 21, 7, {}, self.rules, self.now)
        self.person['job'].update(job_id=21, source_id=7, job_start_date=self.now)
        self.settle()
        self.assertEqual(self.source['items']['398']['count'], 2)
        self.assertEqual(self.data['game_state']['resources']['3']['count'], 5000-980)
        self.assertEqual(self.source['local_production_cycle'], 2)

    def test_miss_is_settled_without_item_or_reroll(self):
        with patch.object(c, '_roll', return_value=.99):
            c.advance(self.data, self.now+3600, 3600, self.rules)
        self.assertEqual(self.source['items'], {})
        self.assertEqual(self.data['game_state']['unlock_information']['job_attempts']['21'], 1)
        self.settle()
        self.assertEqual(self.source['items'], {})

    def test_attempt_tiers_are_history_not_worker_charisma(self):
        self.assertEqual(c.reward(self.rules, 21, 11, 0), {'398': 1})
        self.assertEqual(c.reward(self.rules, 21, 12, 0), {'500': 1})

    def test_invalid_collection_is_transactional_and_does_not_collect_neighbour(self):
        self.settle()
        before = copy.deepcopy(self.data)
        for values in (dict(building_type_id=11, location=301),
                       dict(building_type_id=12, location=300),
                       dict(building_type_id=10, location=300)):
            with self.assertRaises(g.ActionError):
                c.collect(self.data, params(**values), self.rules, self.now)
            self.assertEqual(self.data, before)

    def test_inventory_merge_preserves_owned_item_metadata(self):
        self.settle()
        self.data['game_state']['items']['398'] = dict(item_id=398, count=4, layer=8, cooldown=27)
        new = c.collect(self.data, params(building_type_id=11, location=300), self.rules, self.now)
        self.assertEqual(new['game_state']['items']['398']['count'], 5)
        self.assertEqual(new['game_state']['items']['398']['cooldown'], 27)

    def test_no_retroactive_award_after_bounded_offline_window(self):
        self.settle(elapsed=60)
        self.assertTrue(self.source[c.STATE]['settled'])
        self.assertEqual(self.source['items'], {})

    def test_corrupt_staged_item_cannot_partially_credit(self):
        self.source['items'] = {'398': {'count': 1}, '999': {'count': 1}}
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            c.collect(self.data, params(building_type_id=11, location=300), self.rules, self.now)
        self.assertEqual(self.data, before)


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
class OriginalCommercialTests(unittest.TestCase):
    def test_all_seven_original_operator_tables_and_paid_duration(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        for kind in p.COMMERCIAL:
            building = rules['buildings'][str(kind)]
            state = building['state_data']['11']
            self.assertEqual(state['default_length'], 3600)
            job_id = state['active_job']
            all_possible = set()
            for attempts in (0, 12, 36):
                for roll in range(1000):
                    awarded = c.reward(rules, job_id, attempts, roll/1000)
                    self.assertLessEqual(sum(awarded.values()), 1)
                    all_possible.update(map(int, awarded))
            expected = {reward['item_id'] for reward in building['quest_rewards']}
            self.assertEqual(all_possible, expected)
