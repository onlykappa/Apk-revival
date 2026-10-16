"""Skill protocol tests use self-authored rules and fixed clocks, no real saves."""
import copy
import json
import unittest

from apk_revival.meego.engine import local_game as g, skills


class SkillsTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000
        self.people = {str(i): g.villager(i, f'Person {i}', i % 2, [], 1, self.now) for i in range(1, 5)}
        for ident in ('2', '3'):
            self.people[ident]['birthday'] = self.now - 3 * 3600
            self.people[ident]['job']['job_id'] = 2
        self.data = {'game_state': {'all_villagers': self.people, 'items': {},
                                    'buildings': {'10': g.building(10, 30, 1, 100, self.now)}}}
        self.rules = {'items': {'1': {'type': 4, 'target': 'self', 'add_strength': 2,
                                     'add_charisma': -1, 'duration': 0},
                                '2': {'type': 5, 'target': 'self', 'strength': 50},
                                '3': {'type': 4, 'target': 'self', 'add_random_stat': 1},
                                '4': {'type': 4, 'target': 'village', 'add_strength': 1, 'duration': 300}},
                      'buildings': {'30': {'state_data': {
                          '1': {'valid_transitions': [2]},
                          '2': {'active_job': 46, 'max_workers': 2, 'auto_transition': 1}}}}}

    def school(self, students=None):
        return {'source_id': 10, 'building_type_id': 30, 'state': 2,
                'child_villager_ids': [2] if students is None else students}

    def test_permanent_consumable_consumes_once_and_caps_signed_changes(self):
        self.data['game_state']['items']['1'] = {'count': 1}
        person = self.people['1']
        person['stats'].update(strength=1798, charisma=0)
        skills.use_item(self.data, 1, 1, self.rules, self.now)
        self.assertEqual(person['stats']['strength'], 1799)
        self.assertEqual(person['stats']['charisma'], 0)
        self.assertEqual(self.data['game_state']['items']['1']['count'], 0)
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            skills.use_item(self.data, 1, 1, self.rules, self.now)
        self.assertEqual(self.data, before)

    def test_equipment_and_temporary_village_item_never_modify_base_stats(self):
        for ident in ('2', '4'):
            self.data['game_state']['items'][ident] = {'count': 1}
            before = copy.deepcopy(self.data)
            with self.assertRaises(g.ActionError):
                skills.use_item(self.data, 1, ident, self.rules, self.now)
            self.assertEqual(self.data, before)

    def test_random_stat_is_one_stat_and_restart_deterministic(self):
        self.data['game_state']['items']['3'] = {'count': 1}
        restored = json.loads(json.dumps(self.data))
        skills.use_item(self.data, 1, 3, self.rules, self.now)
        skills.use_item(restored, 1, 3, self.rules, self.now)
        self.assertEqual(self.data, restored)
        self.assertEqual(sum(self.people['1']['stats'][s] for s in skills.STATS), 31)

    def test_positive_consumable_preserves_above_cap_existing_stats(self):
        self.people['1']['stats']['strength'] = 2500
        self.data['game_state']['items']['1'] = {'count': 1}
        skills.use_item(self.data, 1, 1, self.rules, self.now)
        self.assertEqual(self.people['1']['stats']['strength'], 2500)

    def test_assigned_consumable_uses_ownership_on_selected_villager(self):
        self.people['1']['items']['1'] = {'count': 1, 'layer': 8}
        self.data['game_state']['items']['1'] = {'count': 0}
        skills.use_item(self.data, 1, 1, self.rules, self.now)
        self.assertEqual(self.people['1']['stats']['strength'], 12)
        self.assertEqual(self.people['1']['items']['1']['count'], 0)
        self.assertEqual(self.data['game_state']['items']['1']['count'], 0)

    def test_productive_work_gains_accumulate_only_credited_units_and_persist(self):
        self.assertEqual(skills.credit_work(self.data, 1, 16, 59, self.now), 0)
        restored = json.loads(json.dumps(self.data))
        self.assertEqual(skills.credit_work(restored, 1, 16, 1, self.now + 10), 1)
        self.assertEqual(restored['game_state']['all_villagers']['1']['stats']['strength'], 11)
        self.assertEqual(skills.credit_work(restored, 1, 20, 120, self.now + 20), 2)
        self.assertEqual(restored['game_state']['all_villagers']['1']['stats']['intelligence'], 12)
        before = copy.deepcopy(restored)
        for job in (0, 5, 21, 46):
            self.assertEqual(skills.credit_work(restored, 1, job, 500, self.now), 0)
        self.assertEqual(restored, before)
        self.assertNotIn('skill_progress', restored['game_state'])

    def test_multi_unit_delivery_crosses_threshold_and_preserves_remainder(self):
        skills.credit_work(self.data, 1, 16, 57, self.now)
        self.assertEqual(skills.credit_work(self.data, 1, 16, 5, self.now + 12), 1)
        self.assertEqual(self.people['1']['stats']['strength'], 11)
        self.assertEqual(self.data['skill_progress']['1']['strength'], 2)
        self.assertEqual(self.people['1']['last_update'], self.now + 12)

    def test_work_progress_survives_job_changes_and_keeps_stats_independent(self):
        skills.credit_work(self.data, 1, 16, 30, self.now)
        skills.credit_work(self.data, 1, 17, 29, self.now + 12)
        skills.credit_work(self.data, 1, 20, 59, self.now + 24)
        restored = json.loads(json.dumps(self.data))
        skills.credit_work(restored, 1, 18, 1, self.now + 36)
        self.assertEqual(restored['game_state']['all_villagers']['1']['stats'],
                         {**self.people['1']['stats'], 'strength': 11})
        self.assertEqual(restored['skill_progress']['1'], {'strength': 0, 'intelligence': 59})
        skills.credit_work(restored, 1, 20, 1, self.now + 48)
        self.assertEqual(restored['game_state']['all_villagers']['1']['stats']['intelligence'], 11)

    def test_credited_units_are_partition_and_restart_independent(self):
        single = copy.deepcopy(self.data)
        skills.credit_work(single, 1, 16, 137, self.now + 120)
        split = copy.deepcopy(self.data)
        for amount in (1, 5, 53, 1, 60, 17):
            split = json.loads(json.dumps(split))
            skills.credit_work(split, 1, 16, amount, self.now + 120)
        self.assertEqual(single, split)
        self.assertEqual(single['skill_progress']['1']['strength'], 17)
        self.assertEqual(single['game_state']['all_villagers']['1']['stats']['strength'], 12)

    def test_unit_migration_preserves_earned_stats_and_unfinished_legacy_progress(self):
        self.people['1']['stats']['strength'] = 11
        self.data['skill_progress'] = {'1': {'strength': 52}, '2': {'strength': 6},
                                       '3': {'strength': 38, 'intelligence': 4}}
        before = copy.deepcopy(self.data)
        self.assertTrue(skills.migrate_work_progress(self.data))
        self.assertEqual(self.data['game_state'], before['game_state'])
        self.assertEqual(self.data['skill_progress'], before['skill_progress'])
        restored = json.loads(json.dumps(self.data))
        self.assertFalse(skills.migrate_work_progress(restored))
        self.assertEqual(restored, self.data)
        self.assertEqual(skills.credit_work(restored, 1, 16, 8, self.now + 12), 1)
        self.assertEqual(restored['game_state']['all_villagers']['1']['stats']['strength'], 12)
        self.assertEqual(restored['skill_progress']['1']['strength'], 0)
        self.assertEqual(restored['local_migrations'].count(skills.WORK_PROGRESS_MIGRATION), 1)

    def test_no_delivery_or_invalid_amount_never_changes_progress(self):
        before = copy.deepcopy(self.data)
        self.assertEqual(skills.credit_work(self.data, 1, 16, 0, self.now), 0)
        self.assertEqual(self.data, before)
        self.assertEqual(skills.credit_work(self.data, 1, 5, 60, self.now), 0)
        self.assertEqual(self.data, before)
        for amount in (-1, 1.5, True):
            with self.subTest(amount=amount), self.assertRaises(g.ActionError):
                skills.credit_work(self.data, 1, 16, amount, self.now)
            self.assertEqual(self.data, before)
        with self.assertRaises(g.ActionError):
            skills.credit_work(self.data, 999, 16, 60, self.now)
        self.assertEqual(self.data, before)

    def test_school_completion_restart_and_reports_are_exactly_once(self):
        skills.start_school(self.data, 1, self.school(), self.rules, self.now)
        self.assertEqual(self.people['1']['job']['job_id'], 46)
        self.assertEqual(self.people['2']['job']['job_id'], 47)
        self.assertEqual(skills.advance_school(self.data, self.now + 3599), 0)
        restored = json.loads(json.dumps(self.data))
        self.assertEqual(skills.advance_school(restored, self.now + 3600), 1)
        self.assertEqual(skills.advance_school(restored, self.now + 7200), 0)
        person = restored['game_state']['all_villagers']['2']
        self.assertEqual(person['stats']['intelligence'], 11)
        self.assertEqual(person['job']['job_id'], 48)
        output = skills.collect_reports(restored, 10, self.now + 3600)
        self.assertEqual(output['report_cards'], {'2': {'success': 1, 'stat_count': 1, 'stat': 'INT'}})
        self.assertEqual(output['game_state']['all_villagers']['2']['job']['job_id'], 2)
        self.assertEqual(skills.collect_reports(restored, 10, self.now + 3600)['report_cards'], {})
        self.assertEqual(person['stats']['intelligence'], 11)
        output['game_state']['all_villagers']['2']['stats']['intelligence'] = 999
        self.assertEqual(person['stats']['intelligence'], 11)

    def test_invalid_school_requests_are_atomic(self):
        invalid = [self.school([]), self.school([2, 3]), self.school([1]),
                   {**self.school(), 'state': 0}, {**self.school(), 'building_type_id': 1}]
        for request in invalid:
            before = copy.deepcopy(self.data)
            with self.assertRaises(g.ActionError):
                skills.start_school(self.data, 1, request, self.rules, self.now)
            self.assertEqual(self.data, before)
        self.people['2']['birthday'] = self.now - 9.5 * 3600
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            skills.start_school(self.data, 1, self.school(), self.rules, self.now)
        self.assertEqual(self.data, before)

    def test_missing_school_cancels_training_without_reward(self):
        skills.start_school(self.data, 1, self.school(), self.rules, self.now)
        del self.data['game_state']['buildings']['10']
        self.assertEqual(skills.advance_school(self.data, self.now + 3600), 0)
        self.assertEqual(self.people['2']['stats']['intelligence'], 10)
        self.assertEqual(self.people['2']['job']['job_id'], 2)
        self.assertEqual(self.data['school_sessions'], {})

    def test_reassigned_teacher_cancels_before_deadline_without_reward(self):
        skills.start_school(self.data, 1, self.school(), self.rules, self.now)
        teacher_job = g.idle_job(self.now + 10)
        teacher_job.update(job_id=16, source_id=99)
        self.people['1']['job'] = teacher_job
        self.assertEqual(skills.advance_school(self.data, self.now + 10), 0)
        self.assertEqual(self.people['1']['job'], teacher_job)
        self.assertEqual(self.people['2']['job']['job_id'], 2)
        self.assertEqual(self.people['2']['stats']['intelligence'], 10)
        self.assertEqual(self.data['game_state']['buildings']['10']['state'], 1)
        self.assertEqual(self.data['game_state']['buildings']['10']['expire_date'], 0)
        restored = json.loads(json.dumps(self.data))
        self.assertEqual(skills.advance_school(restored, self.now + 7200), 0)
        self.assertEqual(skills.collect_reports(restored, 10, self.now + 7200)['report_cards'], {})

    def test_missing_teacher_after_restart_never_awards_a_student(self):
        skills.start_school(self.data, 1, self.school(), self.rules, self.now)
        restored = json.loads(json.dumps(self.data))
        del restored['game_state']['all_villagers']['1']
        skills.advance_school(restored, self.now + 3600)
        self.assertEqual(restored['game_state']['all_villagers']['2']['stats']['intelligence'], 10)
        self.assertEqual(skills.collect_reports(restored, 10, self.now + 3600)['report_cards'], {})

    def test_interrupted_student_cancels_empty_class_and_releases_teacher(self):
        skills.start_school(self.data, 1, self.school(), self.rules, self.now)
        self.people['2']['job'] = g.idle_job(self.now + 5)
        self.assertEqual(skills.advance_school(self.data, self.now + 5), 0)
        self.assertEqual(self.people['1']['job']['job_id'], 0)
        self.assertEqual(self.people['2']['stats']['intelligence'], 10)

    def test_school_teacher_interruption_through_real_simulation_and_restart(self):
        from apk_revival.meego.engine import simulation as sim
        old_rules = g.RULES
        self.addCleanup(setattr, g, 'RULES', old_rules)
        g.RULES = copy.deepcopy(self.rules)
        g.RULES['buildings']['1'] = {'state_data': {'1': {
            'villager_slots': 5, 'temple_level': 1,
            'resource_caps': {str(i): 100 for i in range(1, 6)}}}}
        g.RULES['jobs'] = {'0': {'active': True, 'type': 0},
                           '2': {'active': True, 'type': 6},
                           '46': {'active': True, 'type': 13},
                           '47': {'active': True, 'type': 12},
                           '48': {'active': True, 'type': 14}}
        self.people['1']['birthday'] = self.now - 20 * 3600
        self.people['4']['birthday'] = self.now - 20 * 3600
        self.data.update(game_user={'user_id': 1}, last_simulated_at=self.now,
                         local_migrations=['starter-economy-1', 'completed-trips-2'])
        self.data['game_state'].update(
            resources={str(i): {'count': 0, 'last_update': self.now} for i in range(1, 6)},
            global_state={}, achievements={})
        self.data['game_state']['buildings']['1'] = g.building(1, 1, 1, 100, self.now)
        started = sim.mutate(self.data, 'game/village/set_job',
                             {'villager_id': ['1'], 'job_id': ['46'],
                              'job_data': [json.dumps(self.school())]}, self.now)
        stopped = sim.mutate(started, 'game/village/set_job',
                             {'villager_id': ['1'], 'job_id': ['0']}, self.now + 5)
        advanced = sim.advance(json.loads(json.dumps(stopped)), self.now + 10)
        self.assertEqual(advanced['game_state']['all_villagers']['2']['job']['job_id'], 2)
        self.assertEqual(advanced['game_state']['all_villagers']['2']['stats']['intelligence'], 10)
        self.assertEqual(advanced['game_state']['buildings']['10']['state'], 1)
        self.assertEqual(advanced['school_sessions'], {})
        resumed = sim.advance(advanced, self.now + 3600)
        self.assertEqual(skills.collect_reports(resumed, 10, self.now + 3600)['report_cards'], {})
        self.assertEqual(resumed['game_state']['all_villagers']['2']['stats']['intelligence'], 10)


class ProductiveUnitIntegrationTests(unittest.TestCase):
    """Exercise actual delivery clipping and credit through the simulation."""

    def setUp(self):
        from apk_revival.meego.engine import simulation as sim
        self.sim = sim
        self.now = 1_000_000
        old_rules = g.RULES
        self.addCleanup(setattr, g, 'RULES', old_rules)
        g.RULES = {
            'buildings': {
                '1': {'state_data': {'1': {'villager_slots': 5, 'temple_level': 1,
                    'resource_caps': {str(i): 100 for i in range(1, 6)}}}},
                '2': {'state_data': {'1': {'active_job': 16, 'default_length': 1}}},
            },
            'jobs': {'0': {'type': 0}, '16': {'type': 3, 'product_type': 359}},
            'items': {}, 'points_store': {},
        }
        person = g.villager(1, 'Fixture', 1, [], 7, self.now)
        person['stats']['strength'] = 410  # Local yield cap: five units/trip.
        person['job'].update(job_id=16, source_id=2, target_id=2, destination_id=1,
                            gather_rate=5, gather_time=8, trip_time=12,
                            local_trip_seconds=0, local_fraction=0)
        self.data = {
            'game_user': {'user_id': 7}, 'last_simulated_at': self.now,
            'local_migrations': ['starter-economy-1', 'completed-trips-2'],
            'skill_progress': {'1': {'strength': 57}},
            'game_state': {
                'all_villagers': {'1': person},
                'buildings': {'1': g.building(1, 1, 1, 100, self.now),
                              '2': g.building(2, 2, 1, 200, self.now)},
                'resources': {str(i): {'resource_id': i, 'count': 0, 'last_update': self.now}
                              for i in range(1, 6)},
                'global_state': {}, 'points': 0, 'achievements': {},
            },
        }
        self.data['game_state']['buildings']['2']['count'] = 100

    def test_actual_multi_unit_delivery_awards_one_point_not_one_trip(self):
        result = self.sim.advance(self.data, self.now + 12)
        self.assertEqual(result['game_state']['resources']['1']['count'], 5)
        self.assertEqual(result['game_state']['all_villagers']['1']['stats']['strength'], 411)
        self.assertEqual(result['skill_progress']['1']['strength'], 2)
        self.assertEqual(self.data['skill_progress']['1']['strength'], 57)

    def test_partial_storage_delivery_only_credits_delivered_units(self):
        self.data['skill_progress']['1']['strength'] = 56
        self.data['game_state']['resources']['1']['count'] = 97
        result = self.sim.advance(self.data, self.now + 12)
        self.assertEqual(result['game_state']['resources']['1']['count'], 100)
        self.assertEqual(result['game_state']['buildings']['2']['count'], 97)
        self.assertEqual(result['skill_progress']['1']['strength'], 59)
        self.assertEqual(result['game_state']['all_villagers']['1']['stats']['strength'], 410)
        restored = json.loads(json.dumps(result))
        blocked = self.sim.advance(restored, self.now + 24)
        self.assertEqual(blocked['skill_progress'], result['skill_progress'])
        self.assertEqual(blocked['game_state']['buildings']['2']['count'], 97)
        blocked['game_state']['resources']['1']['count'] = 95
        resumed = self.sim.advance(blocked, self.now + 36)
        self.assertEqual(resumed['skill_progress']['1']['strength'], 4)
        self.assertEqual(resumed['game_state']['all_villagers']['1']['stats']['strength'], 411)

    def test_partial_final_stock_credits_once_and_missing_source_grants_nothing(self):
        self.data['game_state']['buildings']['2']['count'] = 2
        result = self.sim.advance(self.data, self.now + 12)
        self.assertEqual(result['game_state']['resources']['1']['count'], 2)
        self.assertEqual(result['skill_progress']['1']['strength'], 59)
        self.assertNotIn('2', result['game_state']['buildings'])
        self.assertEqual(result['game_state']['all_villagers']['1']['job']['job_id'], 0)
        restored = json.loads(json.dumps(result))
        later = self.sim.advance(restored, self.now + 24)
        self.assertEqual(later['skill_progress'], result['skill_progress'])
        self.assertEqual(later['game_state']['resources']['1']['count'], 2)


if __name__ == '__main__':
    unittest.main()
