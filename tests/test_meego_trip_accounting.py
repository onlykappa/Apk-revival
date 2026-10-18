"""Conservation checks for timed gather trips using only authored fixtures."""
import copy
import json
import unittest

from apk_revival.meego.engine import local_game as g, simulation as sim


class CompletedTripAccountingTests(unittest.TestCase):
    def setUp(self):
        self.old_rules = g.RULES
        g.RULES = {
            'buildings': {
                '1': {'state_data': {'1': {'villager_slots': 5, 'temple_level': 1,
                                          'resource_caps': {str(i): 100 for i in range(1, 6)}}}},
                '2': {'state_data': {'1': {'active_job': 16, 'default_length': 1}}},
            },
            'jobs': {'0': {'type': 0}, '16': {'type': 3, 'product_type': 359}},
            'items': {}, 'points_store': {},
        }
        self.now = 1000000
        self.data = {
            'game_user': {'user_id': 7}, 'last_simulated_at': self.now,
            'local_migrations': ['starter-economy-1', 'completed-trips-2'],
            'game_state': {
                'all_villagers': {},
                'buildings': {'1': g.building(1, 1, 1, 100, self.now),
                              '2': g.building(2, 2, 1, 200, self.now)},
                'resources': {str(i): {'resource_id': i, 'count': 0, 'last_update': self.now}
                              for i in range(1, 6)},
                'global_state': {}, 'points': 0, 'achievements': {},
            },
        }
        self.data['game_state']['buildings']['2']['count'] = 100
        self.add_worker(1)
        # Explicit test stock is already using the new capacity policy.
        from apk_revival.meego.engine import ecology
        ecology.register_stock(self.data, self.data['game_state']['buildings']['2'], 250)

    def tearDown(self):
        g.RULES = self.old_rules

    def add_worker(self, ident, strength=10):
        person = g.villager(ident, 'Fixture', 1, [313, 317, 322, 329, 339], 7, self.now)
        person['birthday'] = self.now - 20 * 3600
        person['stats']['strength'] = strength
        person['job'].update(job_id=16, source_id=2, target_id=2, destination_id=1,
                             gather_rate=sim.gather_amount(person, 16), gather_time=8,
                             trip_time=12, local_trip_seconds=0, local_fraction=0)
        self.data['game_state']['all_villagers'][str(ident)] = person
        return person

    def advance_segments(self, data, elapsed, *, restart=False):
        when = self.now
        for seconds in elapsed:
            when += seconds
            data = sim.advance(data, when)
            if restart:
                data = json.loads(json.dumps(data))
        return data

    def totals(self, data):
        gs = data['game_state']
        earned = gs['resources']['1']['count']
        remaining = gs['buildings'].get('2', {}).get('count', 0)
        return earned, remaining

    def test_partial_trips_conserve_stock_across_segments_and_restart(self):
        before = copy.deepcopy(self.data)
        result = self.advance_segments(self.data, [3, 8, 1, 5, 7, 23, 1], restart=True)
        self.assertEqual(self.totals(result), (80, 20))
        self.assertEqual(sum(self.totals(result)), 100)
        self.assertEqual(result['skill_progress']['1']['strength'], 20)
        self.assertEqual(result['game_state']['all_villagers']['1']['job']['local_trip_seconds'], 0)
        self.assertEqual(self.data, before)
        single = sim.advance(self.data, self.now + 48)
        self.assertEqual(self.totals(single), self.totals(result))
        self.assertEqual(single['skill_progress'], result['skill_progress'])

    def test_two_workers_deplete_shared_finite_stock_exactly_once(self):
        self.add_worker(2)
        self.data['game_state']['buildings']['2']['count'] = 5
        result = self.advance_segments(self.data, [11, 1, 12, 12], restart=True)
        self.assertEqual(self.totals(result), (5, 0))
        self.assertNotIn('2', result['game_state']['buildings'])
        self.assertTrue(all(p['job']['job_id'] == 0 for p in result['game_state']['all_villagers'].values()))
        self.assertEqual(sum(p.get('strength', 0) for p in result['skill_progress'].values()), 5)
        later = sim.advance(result, self.now + 120)
        self.assertEqual(self.totals(later), (5, 0))
        self.assertEqual(later['skill_progress'], result['skill_progress'])

    def test_full_warehouse_consumes_no_stock_and_grants_no_work_progress(self):
        self.data['game_state']['resources']['1']['count'] = 100
        self.data['skill_progress'] = {'1': {'strength': 59}}
        result = self.advance_segments(self.data, [6, 6, 12, 120], restart=True)
        self.assertEqual(self.totals(result), (100, 100))
        self.assertEqual(result['skill_progress'], self.data['skill_progress'])
        self.assertEqual(result['game_state']['all_villagers']['1']['stats']['strength'], 10)
        # Space becoming available allows a future trip; missed full-warehouse
        # cycles do not become a resource or XP backlog.
        result['game_state']['resources']['1']['count'] = 98
        result = sim.advance(result, self.now + 144 + 12)
        self.assertEqual(self.totals(result), (100, 98))
        self.assertEqual(result['game_state']['all_villagers']['1']['stats']['strength'], 11)
        self.assertEqual(result['skill_progress']['1']['strength'], 1)

    def test_partial_warehouse_credit_never_consumes_uncredited_stock_or_xp(self):
        self.data['game_state']['resources']['1']['count'] = 98
        result = sim.advance(self.data, self.now + 120)
        self.assertEqual(self.totals(result), (100, 98))
        self.assertEqual(result['skill_progress']['1']['strength'], 2)

    def test_fractional_yields_are_independent_of_poll_segmentation_and_restart(self):
        for strength, trips, expected in [(12, 2, 40), (15, 2, 42), (13, 2, 41)]:
            with self.subTest(strength=strength):
                self.add_worker(1, strength=strength)
                single = sim.advance(self.data, self.now + trips * 12)
                many = self.advance_segments(self.data, [5, 7] * trips, restart=True)
                self.assertEqual(self.totals(single), (expected, 100 - expected))
                self.assertEqual(self.totals(many), self.totals(single))
                self.assertEqual(many['skill_progress'], single['skill_progress'])
                self.assertAlmostEqual(many['game_state']['all_villagers']['1']['job']['local_fraction'],
                                       single['game_state']['all_villagers']['1']['job']['local_fraction'])

    def test_strength_24_preserves_fraction_across_two_trips(self):
        self.add_worker(1, strength=24)
        self.assertAlmostEqual(sim.gather_amount(self.data['game_state']['all_villagers']['1'],16),22.8)
        result = self.advance_segments(self.data, [12] * 2, restart=True)
        self.assertEqual(self.totals(result), (45,55))
        self.assertEqual(result['skill_progress']['1']['strength'],45)
        self.assertAlmostEqual(result['game_state']['all_villagers']['1']['job']['local_fraction'],.6)

    def test_strength_progression_and_cap_do_not_change_research(self):
        person = self.data['game_state']['all_villagers']['1']
        for strength, expected in ((0,20),(10,20),(20,22),(24,22.8),(30,24),(40,26),(50,28),(100,38),(1799,377.8)):
            person['stats']['strength']=strength
            for job in (16,17,18):
                self.assertAlmostEqual(sim.gather_amount(person,job),expected)
            self.assertEqual(sim.gather_amount(person,20),1)
        person['stats']['intelligence']=110
        self.assertEqual(sim.gather_amount(person,20),2)

    def test_rollback_and_repeated_clock_never_credit_or_rewind_trip_progress(self):
        result = sim.advance(self.data, self.now + 15)
        self.assertEqual(self.totals(result), (20, 80))
        self.assertEqual(result['game_state']['all_villagers']['1']['job']['local_trip_seconds'], 3)
        before = copy.deepcopy(result)
        self.assertEqual(sim.advance(result, self.now + 14), before)
        self.assertEqual(sim.advance(result, self.now + 15), before)
        resumed = sim.advance(result, self.now + 24)
        self.assertEqual(self.totals(resumed), (40, 60))
        self.assertEqual(resumed['skill_progress']['1']['strength'], 40)

    def test_growth_boundaries_keep_yield_equal_across_polling_and_restart(self):
        g.RULES['buildings']['1']['state_data']['1']['resource_caps']['1'] = 10000
        self.data['game_state']['buildings']['2']['count'] = 10000
        single = sim.advance(self.data, self.now + 160 * 12)
        split = self.advance_segments(self.data, [720, 1200], restart=True)
        frequent = self.advance_segments(self.data, [11, 1] * 160, restart=True)
        self.assertGreater(self.totals(single)[0], 3200)
        self.assertEqual(sum(self.totals(single)), 10000)
        for result in (split, frequent):
            self.assertEqual(self.totals(result), self.totals(single))
            self.assertEqual(result['skill_progress'], single['skill_progress'])
            self.assertEqual(result['game_state']['all_villagers']['1']['stats'],
                             single['game_state']['all_villagers']['1']['stats'])
            self.assertEqual(result['game_state']['all_villagers']['1']['job']['local_fraction'],
                             single['game_state']['all_villagers']['1']['job']['local_fraction'])

    def test_growth_boundary_near_storage_cap_does_not_credit_blocked_work(self):
        self.data['skill_progress'] = {'1': {'strength': 59}}
        self.data['game_state']['resources']['1']['count'] = 95
        single = sim.advance(self.data, self.now + 120)
        many = self.advance_segments(self.data, [12] * 10, restart=True)
        for result in (single, many):
            self.assertEqual(self.totals(result), (100, 95))
            self.assertEqual(result['skill_progress']['1']['strength'], 4)
            self.assertEqual(result['game_state']['all_villagers']['1']['stats']['strength'], 11)
            self.assertEqual(result['game_state']['all_villagers']['1']['job']['local_fraction'], 0)


if __name__ == '__main__':
    unittest.main()

