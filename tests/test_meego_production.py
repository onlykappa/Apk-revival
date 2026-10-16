"""Private original-TechTree checks with synthetic villages and clocks only."""
import copy
import os
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import local_game as g, production as p


def params(**values):
    return {key: [str(value)] for key, value in values.items()}


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
class OriginalProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            tree = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        cls.rules = {key: tree[key] for key in ('buildings', 'jobs', 'items')}

    def setUp(self):
        self.now = 1_000_000
        self.data = {'game_state': {
            'points': 20,
            'resources': {str(i): {'count': 1_000_000, 'last_update': self.now} for i in range(1, 6)},
            'achievements': {'102': {'level': 15}},
            'buildings': {'7': g.building(7, 10, 1, 300, self.now)},
            'all_villagers': {'1': g.villager(1, 'Test', 1, [], 3, self.now)},
        }}

    def building(self, data=None):
        return (self.data if data is None else data)['game_state']['buildings']['7']

    def change(self, target, data=None):
        source = self.building(data)
        return p.change_building(self.data if data is None else data,
                                 params(building_id=7, building_type_id=source['building_type'], state=target),
                                 self.rules, self.now)

    def assign(self, data, job_id, extra=None):
        gs = data['game_state']
        p.activate_for_job(gs, job_id, 7, extra or {}, self.rules, self.now)
        job = g.idle_job(self.now)
        job.update(job_id=job_id, source_id=7, target_id=7)
        p.configure_job(self.building(data), job, self.rules, self.now)
        gs['all_villagers']['1']['job'] = job

    def test_three_original_factories_complete_first_cycle_with_finite_count(self):
        for kind, job_id, length, count in ((10, 30, 900, 6500),
                                          (13, 24, 1350, 17000),
                                          (16, 28, 1080, 19500)):
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.data)
                self.building(data)['building_type'] = kind
                self.assign(data, job_id)
                self.assertEqual(self.building(data)['state'], 11)
                self.assertEqual(self.building(data)['expire_date'], self.now + length)
                p.advance_cycles(data, self.now + length - 1, length - 1, self.rules)
                self.assertEqual(self.building(data)['state'], 11)
                p.advance_cycles(data, self.now + length, 1, self.rules)
                source = self.building(data)
                self.assertEqual((source['state'], source['count']), (12, count))
                self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)
                self.assertEqual(p.consume_stock(data['game_state'], source, count, self.rules, self.now + length), 0)
                self.assertEqual(source['state'], 1)
                self.assertEqual(self.building()['state'], 1)

    def test_stocking_requires_worker_and_pauses_without_catchup(self):
        data = self.change(11)
        p.advance_cycles(data, self.now + 100, 100, self.rules)
        self.assertEqual(self.building(data)['progress'], 0)
        self.now += 100
        self.assign(data, 30)
        p.advance_cycles(data, self.now + 10, 10, self.rules)
        self.assertEqual(self.building(data)['progress'], 10)
        data['game_state']['all_villagers']['1']['job'] = g.idle_job(self.now + 10)
        p.advance_cycles(data, self.now + 1000, 990, self.rules)
        self.assertEqual(self.building(data)['progress'], 10)
        self.assertEqual(self.building(data)['expire_date'], 0)

    def test_same_clock_retry_or_duplicate_workers_does_not_duplicate_progress(self):
        data = copy.deepcopy(self.data)
        self.assign(data, 30)
        person = copy.deepcopy(data['game_state']['all_villagers']['1'])
        person['villager_id'] = 2
        data['game_state']['all_villagers']['2'] = person
        p.advance_cycles(data, self.now + 10, 10, self.rules)
        self.assertEqual(self.building(data)['progress'], 10)
        before = copy.deepcopy(data)
        p.advance_cycles(data, self.now + 10, 10, self.rules)
        self.assertEqual(data, before)

    def test_stocked_final_item_resets_source_without_deleting_building(self):
        source = self.building()
        source.update(state=12, count=1)
        job = self.data['game_state']['all_villagers']['1']['job']
        job.update(job_id=19, source_id=7)
        result = p.consume_stock(self.data['game_state'], source, 1, self.rules, self.now)
        self.assertEqual(result, 0)
        self.assertEqual(source['state'], 1)
        self.assertIn('7', self.data['game_state']['buildings'])
        self.assertEqual(self.data['game_state']['all_villagers']['1']['job']['job_id'], 0)

    def test_clipped_delivery_only_consumes_credited_units(self):
        source = self.building()
        source.update(state=12, count=5)
        self.assertEqual(p.consume_stock(self.data['game_state'], source, 0, self.rules, self.now), 5)
        self.assertEqual(p.consume_stock(self.data['game_state'], source, 2, self.rules, self.now), 3)
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            p.consume_stock(self.data['game_state'], source, 4, self.rules, self.now)
        self.assertEqual(self.data, before)

    def test_cannot_skip_stocking_or_reset_stock_to_refill(self):
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            self.change(12)
        self.assertEqual(self.data, before)
        self.building().update(state=12, count=100)
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            self.change(1)
        with self.assertRaises(g.ActionError):
            self.change(11)
        self.assertEqual(self.data, before)

    def test_higher_stocking_tiers_require_original_achievements(self):
        for target, level, amount in ((21, 1, 19500), (31, 2, 40000)):
            with self.subTest(target=target):
                with self.assertRaisesRegex(g.ActionError, 'unlock'):
                    self.change(target)
                self.data['game_state']['achievements']['128'] = {'level': level}
                data = self.change(target)
                self.assign(data, self.rules['buildings']['10']['state_data'][str(target)]['active_job'])
                duration = self.rules['buildings']['10']['state_data'][str(target)]['default_length']
                p.advance_cycles(data, self.now + duration, duration, self.rules)
                self.assertEqual(self.building(data)['count'], amount)

    def test_original_commercial_costs_debit_once_and_expire_at_one_hour(self):
        for kind, job_id, price in ((11, 21, 490), (12, 27, 490),
                                    (14, 26, 535), (18, 37, 535),
                                    (19, 31, 700), (20, 36, 750),
                                    (21, 38, 750)):
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.data)
                self.building(data)['building_type'] = kind
                before_food = data['game_state']['resources']['3']['count']
                self.assign(data, job_id, params(state=1, building_type_id=kind))
                self.assertEqual(data['game_state']['resources']['3']['count'], before_food - price)
                self.assertEqual(self.building(data)['expire_date'], self.now + 3600)
                retry = p.change_building(data, params(building_id=7, building_type_id=kind, state=11), self.rules, self.now + 10)
                self.assertEqual(retry, data)
                p.advance_cycles(data, self.now + 3599, 3599, self.rules)
                self.assertEqual(self.building(data)['state'], 11)
                p.advance_cycles(data, self.now + 3600, 1, self.rules)
                self.assertEqual(self.building(data)['state'], 1)
                self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)

    def test_insufficient_commercial_food_leaves_original_save_unchanged(self):
        self.building()['building_type'] = 11
        self.data['game_state']['resources']['3']['count'] = 489
        before = copy.deepcopy(self.data)
        with self.assertRaisesRegex(g.ActionError, 'resources'):
            self.change(11)
        self.assertEqual(self.data, before)

    def test_cycle_id_advances_only_for_new_activation(self):
        data = self.change(11)
        self.assertEqual(self.building(data)['local_production_cycle'], 1)
        retry = self.change(11, data)
        self.assertEqual(retry, data)
        self.assign(data, 30)
        p.advance_cycles(data, self.now + 900, 900, self.rules)
        p.consume_stock(data['game_state'], self.building(data), 6500, self.rules, self.now + 900)
        data = self.change(11, data)
        self.assertEqual(self.building(data)['local_production_cycle'], 2)

    def test_stale_assignment_after_full_stocking_does_not_restart(self):
        data = copy.deepcopy(self.data)
        self.assign(data, 30)
        p.advance_cycles(data, self.now + 900, 900, self.rules)
        before = copy.deepcopy(data)
        self.assertFalse(p.activate_for_job(data['game_state'], 30, 7, {}, self.rules, self.now + 901))
        self.assertEqual(data, before)

    def test_rule_construction_goes_to_existing_construction_handler(self):
        self.assertIsNone(self.change(0))

    def test_all_nine_original_tiers_honor_unlock_duration_and_stock_budget(self):
        for kind in sorted(p.INDUSTRIAL):
            states = self.rules['buildings'][str(kind)]['state_data']
            for target in (11, 21, 31):
                with self.subTest(kind=kind, target=target):
                    data = copy.deepcopy(self.data)
                    self.building(data)['building_type'] = kind
                    rule = states[str(target)]
                    if rule.get('unlock_achievement_id'):
                        data['game_state']['achievements'][str(rule['unlock_achievement_id'])] = {'level': rule['unlock_achievement_level']}
                    self.assign(data, rule['active_job'])
                    duration = rule['default_length']
                    p.advance_cycles(data, self.now + duration, duration, self.rules)
                    source = self.building(data)
                    self.assertEqual(source['state'], rule['auto_transition'])
                    self.assertEqual(source['count'], states[str(rule['auto_transition'])]['default_length'])
                    p.consume_stock(data['game_state'], source, source['count'], self.rules, self.now + duration)
                    self.assertEqual(source['state'], 1)

    def test_stopped_stocking_can_resume_without_restart_or_extra_cycle(self):
        data = copy.deepcopy(self.data)
        self.assign(data, 30)
        p.advance_cycles(data, self.now + 100, 100, self.rules)
        data['game_state']['all_villagers']['1']['job'] = g.idle_job(self.now + 100)
        p.advance_cycles(data, self.now + 200, 100, self.rules)
        self.now += 200
        self.assign(data, 30)
        self.assertEqual(self.building(data)['expire_date'], self.now + 800)
        self.assertEqual(self.building(data)['local_production_cycle'], 1)
        p.advance_cycles(data, self.now + 800, 800, self.rules)
        self.assertEqual(self.building(data)['state'], 12)
        self.assertEqual(self.building(data)['count'], 6500)

    def test_depot_accepts_original_temple_storage_and_preserved_upgrade_capacities(self):
        gs = self.data['game_state']
        for kind, state in ((1, 1), (1, 10), (1, 131), (8, 1), (8, 10), (8, 11)):
            with self.subTest(kind=kind, state=state):
                gs['buildings']['9'] = g.building(9, kind, state, 800, self.now)
                self.assertIs(p.validate_depot(gs, 9, 19, self.rules), gs['buildings']['9'])

    def test_depot_rejects_huts_nodes_unbuilt_storage_and_deleted_destination(self):
        gs = self.data['game_state']
        for kind, state in ((1, 0), (8, 0), (5, 1), (2, 1), (10, 12)):
            with self.subTest(kind=kind, state=state):
                gs['buildings']['9'] = g.building(9, kind, state, 800, self.now)
                before = copy.deepcopy(gs)
                with self.assertRaisesRegex(g.ActionError, 'depot|receive'):
                    p.validate_depot(gs, 9, 19, self.rules)
                self.assertEqual(gs, before)
        del gs['buildings']['9']
        with self.assertRaises(g.ActionError):
            p.validate_depot(gs, 9, 19, self.rules)

