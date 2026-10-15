"""Synthetic clocks/saves and optional privately-owned original TechTree checks."""
import copy
import json
import os
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import adventures as a, local_game as g


def params(**kw):
    return {k: [str(v)] for k, v in kw.items()}


def fixture_rules():
    # Small authored fixture: the original APK is not redistributed in tests.
    buildings = {}
    jobs = {'0': {'interruptible': 1}}
    definitions = [(35, 52, 20, 2), (42, 62, 30, 5), (36, 53, 140, 11),
                   (37, 54, 3, 1), (40, 59, 4, 2), (38, 56, 50, 10), (41, 60, 60, 24)]
    for kind, jid, duration, gold in definitions:
        states = {'1': {'valid_transitions': [11], 'default_length': 0},
                  '11': {'active_job': jid, 'default_length': duration, 'auto_transition': 1,
                         'valid_transitions': [1], 'counter_unit_cost': {}}}
        allowed_states = [1, 11]
        if jid in (54, 59):
            states['1']['valid_transitions'] = [11]
            allowed_states = [11]
        if jid in (56, 60):
            states['11']['auto_transition'] = 21
            states['21'] = {'stocked_phase': True, 'active_job': 58 if kind == 38 else 61, 'default_length': 4 if kind == 38 else 5,
                            'auto_transition': 1, 'valid_transitions': [1]}
        buildings[str(kind)] = {'state_data': states}
        jobs[str(jid)] = {'interruptible': 0, 'default_idle_job_id': 55 if jid in (56, 60) else 0,
                         'valid_transitions': list(a.JOBS | {0, 50}),
                         'parameter_restrictions': {'source_id': [['state', 'in', allowed_states], ['building_type', 'in', [kind]]]},
                         'random_drop': {'0': {'373': {'chance': 100, 'count_contribution': {'constant': gold}}}}}
    for jid in (55, 57):
        jobs[str(jid)] = {'interruptible': 1, 'valid_transitions': list(a.JOBS | {0, 50})}
    for jid, kind, gold in [(58, 38, 2), (61, 41, 4)]:
        jobs[str(jid)] = {'gather_time': 10, 'default_idle_job_id': 57,
                         'parameter_restrictions': {'source_id': [['state', 'in', [21, 31]]]},
                         'valid_transitions': list(a.JOBS | {50}),
                         'random_drop': {'0': {'373': {'chance': 100, 'count_contribution': {'constant': gold}}}}}
    return {'buildings': buildings, 'jobs': jobs,
            'dungeon_types': {'3': {'active': True, 'duration': 330, 'points_cost': 1, 'user_slots': 4,
                                    'stages_count': 1, 'required_keys': [],
                                    'progress': {'breakpoints': {'0': 300, '1': 500, '2': 750, '3': 1000}}},
                              '2': {'active': True, 'duration': 915, 'points_cost': 2, 'user_slots': 8,
                                    'stages_count': 2, 'required_keys': [],
                                    'progress': {'breakpoints': {'0': 1440, '1': 1893, '2': 2347, '3': 2800}}}},
            'dungeon_stages': {
                '5': {'active': True, 'dungeon_type_id': 3, 'stage_level': 0, 'duration': 330,
                      'buildings': {'1110': {'id': 35, 'state': 1}, '1728': {'id': 42, 'state': 1}}},
                '2': {'active': True, 'dungeon_type_id': 2, 'stage_level': 0, 'duration': 420,
                      'buildings': {'1070': {'id': 36, 'state': 1, 'children': {'971': {'active_state': '11', 'inactive_state': '1'}}},
                                    '971': {'id': 37, 'state': 1}}},
                '3': {'active': True, 'dungeon_type_id': 2, 'stage_level': 1, 'duration': 420,
                      'default_jobs': [57, 55], 'buildings': {'1140': {'id': 38, 'state': 21}, '1826': {'id': 41, 'state': 1}}}}}


class AdventureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = fixture_rules()

    def setUp(self):
        self.now = 1_000_000
        self.data = {'game_user': {'user_id': 7, 'username': 'Local'},
                     'game_state': {'points': 20, 'buildings': {'90': g.building(90, 34, 1, 200, self.now)},
                                    'all_villagers': {str(i): g.villager(i, f'Local {i}', 0, [], 7, self.now) for i in range(1, 10)},
                                    'resources': {str(i): {'resource_id': i, 'count': 1000, 'last_update': self.now} for i in range(1, 6)},
                                    'items': {}, 'village_information': {}, 'unlock_information': {}}}

    def call(self, action, at=None, **kw):
        result = a.handle(self.data, 'game/dungeon/' + action, params(**kw), self.rules, self.now if at is None else at)
        self.data, response = result
        return response

    def start(self, kind=3):
        return self.call('start_dungeon', dungeon_type_id=kind, villager_id=1)

    def session(self):
        state = self.data[a.KEY]
        return state['sessions'][str(state['active_id'] or max(map(int, state['sessions'])))]

    def source(self, kind):
        return next(b['building_id'] for b in self.session()['game_state']['buildings'].values() if b['building_type'] == kind)

    def assign(self, jid, kind, person=1, at=None):
        return self.call('set_job', at, job_id=jid, source_id=self.source(kind), villager_id=person)

    def test_expired_dungeon_unloads_native_stage_without_losing_claim_or_people(self):
        self.start()
        packet = self.call('update_dungeon', self.now + 331, dungeon_id=1, current_stage_level=0)
        self.assertIsNone(packet['user_dungeon'])
        self.assertIsNone(packet['dungeon_game_state'])
        self.assertEqual(len(packet['game_state']['all_villagers']), 9)
        self.assertEqual(self.session()['status'], 'finished')
        self.assertEqual(self.data['game_state']['all_villagers']['1']['location_type'], 0)
        self.assertEqual(self.data['game_state']['all_villagers']['1']['job']['job_id'], 50)
        self.assertEqual(packet['game_state']['dungeon_info']['active_dungeons'], {})
        response = self.call('complete_dungeon_quest', self.now + 332, dungeon_id=1, villager_id=1)
        self.assertEqual(response['game_state']['all_villagers']['1']['location_type'], 0)
        self.assertEqual(self.session()['status'], 'claimed')

    def test_native_building_timer_poll_without_state_finishes_work_once(self):
        self.start()
        source_id = self.source(42)
        self.call('set_job', job_id=62, villager_id=1,
                  job_data=json.dumps({'source_id': source_id, 'building_type_id': 42, 'state': 11}))
        packet = self.call('update_building', self.now + 60, dungeon_id=1,
                           building_id=source_id, building_type_id=42)
        self.assertEqual(packet['dungeon_game_state']['buildings'][str(source_id)]['state'], 1)
        gold = self.session()['participants']['1']['gold_count']
        self.assertGreater(gold, 0)
        self.call('update_building', self.now + 61, dungeon_id=1,
                  building_id=source_id, building_type_id=42)
        self.assertEqual(self.session()['participants']['1']['gold_count'], gold)
        with self.assertRaises(g.ActionError):
            self.call('update_building', self.now + 62, dungeon_id=1,
                      building_id=source_id, building_type_id=35)

    def test_offline_notices_keep_typed_stage_and_unload_after_expiry(self):
        self.start()
        response = self.call('get_dungeon_notices', dungeon_id=1)
        self.assertEqual(response['dungeon_notices'], [])
        self.assertEqual(self.call('get_last_viewed_id', dungeon_id=1), 0)
        self.assertEqual(response['dungeon_packet']['user_dungeon']['dungeon_id'], 1)
        response = self.call('get_dungeon_notices', self.now + 331, dungeon_id=1)
        self.assertEqual(response['dungeon_notices'], [])
        self.assertIsNone(response['dungeon_packet']['user_dungeon'])

    def test_fishing_deadline_covers_remaining_stock_and_stopping_clears_timer(self):
        self.start(2)
        self.call('update_dungeon', self.now + 421, dungeon_id=1, current_stage_level=0)
        source = next(b for b in self.session()['game_state']['buildings'].values()
                      if b['building_type'] == 38 and b['state'] == 21)
        source_id = source['building_id']
        self.call('set_job', self.now + 422, villager_id=1, job_id=58, source_id=source_id)
        source = self.session()['game_state']['buildings'][str(source_id)]
        stock = source['count']
        deadline = self.now + 422 + stock * 10
        self.assertEqual(source['expire_date'], deadline)
        before = self.session()['participants']['1']['gold_count']
        self.call('update_building', self.now + 432, dungeon_id=1, building_id=source_id)
        source = self.session()['game_state']['buildings'][str(source_id)]
        self.assertEqual(source['count'], stock - 1)
        self.assertEqual(source['expire_date'], deadline)
        self.assertGreater(self.session()['participants']['1']['gold_count'], before)
        # Simulate the old first-pickup timer and repair it on the next poll.
        source['expire_date'] = self.now + 432
        self.call('update_building', self.now + 433, dungeon_id=1, building_id=source_id)
        self.assertEqual(self.session()['game_state']['buildings'][str(source_id)]['expire_date'], deadline)
        stopped = self.call('set_job', self.now + 434, villager_id=1, job_id=57)
        self.assertEqual(stopped['dungeon_game_state']['buildings'][str(source_id)]['expire_date'], 0)
        self.call('update_building', self.now + 435, dungeon_id=1, building_id=source_id)
        self.assertEqual(self.session()['game_state']['buildings'][str(source_id)]['expire_date'], 0)
        self.assertEqual(self.session()['game_state']['buildings'][str(source_id)]['count'], stock - 1)

    def test_late_timer_and_notice_reads_after_claim_close_without_new_rewards(self):
        self.start()
        self.call('complete_dungeon_quest', self.now + 331, dungeon_id=1, villager_id=1)
        before = copy.deepcopy(self.data)
        packet = self.call('update_dungeon', self.now + 332, dungeon_id=1, current_stage_level=0)
        self.assertIsNone(packet['user_dungeon'])
        self.assertIsNone(packet['dungeon_game_state'])
        self.assertEqual(packet['game_state'], before['game_state'])
        notices = self.call('get_dungeon_notices', self.now + 333, dungeon_id=1)
        self.assertEqual(notices['dungeon_notices'], [])
        self.assertIsNone(notices['dungeon_packet']['user_dungeon'])
        self.assertEqual(self.data, before)

    def test_start_native_packet_has_original_stage_and_isolated_home(self):
        original = copy.deepcopy(self.data)
        packet = self.start()
        self.assertEqual(set(packet), {'game_state', 'user_dungeon', 'dungeon_game_state'})
        self.assertEqual(packet['user_dungeon']['dungeon_type_id'], 3)
        self.assertEqual(packet['user_dungeon']['slots_filled'], 1)
        self.assertEqual(packet['user_dungeon']['dungeon_expire_date'], self.now + 330)
        self.assertEqual(packet['game_state']['points'], 19)
        self.assertEqual(packet['game_state']['all_villagers']['1']['location_type'], 1)
        self.assertEqual(packet['game_state']['resources'], original['game_state']['resources'])
        self.assertTrue(packet['dungeon_game_state']['buildings'])
        self.assertNotEqual(packet['dungeon_game_state']['buildings'], packet['game_state']['buildings'])
        packet['dungeon_game_state']['buildings'].clear()
        self.assertTrue(self.session()['game_state']['buildings'])

    def test_start_retry_does_not_charge_or_reset(self):
        self.start()
        end = self.session()['expire_date']
        self.call('start_dungeon', self.now + 50, dungeon_type_id=3, villager_id=1)
        self.assertEqual(self.data['game_state']['points'], 19)
        self.assertEqual(self.session()['expire_date'], end)

    def test_rejected_start_rolls_back(self):
        for mutation in ['no_portal', 'child', 'foreign', 'broke', 'inactive']:
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation == 'no_portal': self.data['game_state']['buildings'].clear()
                if mutation == 'child': self.data['game_state']['all_villagers']['1']['birthday'] = self.now - 3600
                if mutation == 'foreign': self.data['game_state']['all_villagers']['1']['user_id'] = 8
                if mutation == 'broke': self.data['game_state']['points'] = 0
                old = copy.deepcopy(self.data)
                with self.assertRaises(g.ActionError):
                    self.start(1 if mutation == 'inactive' else 3)
                self.assertEqual(self.data, old)

    def test_job_earns_original_guaranteed_gold_only_after_full_cycle(self):
        self.start()
        self.assign(52, 35)
        self.call('update_villager_job', self.now + 19, villager_id=1)
        self.assertEqual(self.session()['participants']['1']['gold_count'], 0)
        self.call('update_villager_job', self.now + 20, villager_id=1)
        self.assertEqual(self.session()['participants']['1']['gold_count'], 2)
        self.assertEqual(self.session()['participants']['1']['time_worked'], 20)
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1000)
        self.call('get_dungeon', self.now + 100)
        self.assertEqual(self.session()['participants']['1']['gold_count'], 2)

    def test_claim_earned_gold_and_replay_without_resetting_new_progress(self):
        self.start()
        self.assign(62, 42)
        self.data = json.loads(json.dumps(self.data))
        response = self.call('complete_dungeon_quest', self.now + 330, villager_id=1)
        self.assertEqual(response['dungeon_results']['1']['resource_rewards'], {'5': 5})
        self.assertEqual(set(response['dungeon_results']['1']), {'resource_rewards', 'bonus_resource_rewards', 'item_rewards', 'points_reward', 'additional_bonus_rewards'})
        self.assertEqual(response['dungeon_summary']['1']['quest_results']['resources'], {'5': 5})
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1005)
        self.assertEqual(self.data['game_state']['all_villagers']['1']['location_type'], 0)
        self.data['game_state']['resources']['1']['count'] += 17
        replay = self.call('complete_dungeon_quest', self.now + 400, villager_id=1)
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1005)
        self.assertEqual(replay['game_state']['resources']['1']['count'], 1017)
        self.assertEqual(self.data[a.KEY]['active_id'], 0)

    def test_early_claim_and_client_forgery_do_not_award_or_move(self):
        self.start()
        before = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            self.call('complete_dungeon_quest', self.now + 329, villager_id=1, points=999999)
        self.assertEqual(before, self.data)
        self.call('complete_dungeon_quest', self.now + 330, villager_id=1, points=999999)
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1000)
        self.assertEqual(self.data['game_state']['points'], 19)

    def test_second_original_stage_transition_resets_stage_not_accounting(self):
        self.start(2)
        self.assign(53, 36)
        self.call('get_dungeon', self.now + 419)
        self.assertEqual(self.session()['stage_level'], 0)
        packet = self.call('get_dungeon', self.now + 420)
        self.assertEqual(packet['user_dungeon']['stage_level'], 1)
        self.assertIn(38, {b['building_type'] for b in packet['dungeon_game_state']['buildings'].values()})
        self.assertEqual(self.session()['participants']['1']['gold_count'], 11)
        self.assertEqual(self.session()['participants']['1']['time_worked'], 140)
        self.assertEqual(packet['dungeon_game_state']['all_villagers']['1']['job']['job_id'], 57)

    def test_stage_cannot_be_skipped_by_client(self):
        self.start(2)
        old = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError):
            self.call('update_dungeon', self.now + 2, current_stage_level=1)
        self.assertEqual(self.data, old)

    def test_wrong_job_source_and_nonparticipant_are_rejected(self):
        self.start()
        old = copy.deepcopy(self.data)
        for kwargs in [dict(job_id=53, source_id=self.source(35), villager_id=1),
                       dict(job_id=52, source_id=999999, villager_id=1),
                       dict(job_id=52, source_id=self.source(35), villager_id=2)]:
            with self.assertRaises(g.ActionError): self.call('set_job', **kwargs)
            self.assertEqual(self.data, old)

    def test_join_same_villager_is_idempotent_and_capacity_enforced(self):
        self.start()
        self.call('send_villager_to_dungeon', villager_id=1)
        self.assertEqual(len(self.session()['participants']), 1)
        for i in range(2, int(self.rules['dungeon_types']['3']['user_slots']) + 1):
            self.call('send_villager_to_dungeon', villager_id=i)
        with self.assertRaises(g.ActionError): self.call('send_villager_to_dungeon', villager_id=9)
        self.assertEqual(self.data['game_state']['points'], 19)

    def test_claim_each_participant_credits_only_their_work(self):
        self.start()
        self.call('send_villager_to_dungeon', villager_id=2)
        self.assign(52, 35, 1)
        self.assign(62, 42, 2)
        self.call('complete_dungeon_quest', self.now + 330, villager_id=1)
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1002)
        self.call('complete_dungeon_quest', self.now + 330, villager_id=2)
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1007)

    def test_native_update_building_activation_then_assignment_does_not_double_charge(self):
        self.start()
        source = self.source(35)
        response = self.call('update_building', building_id=source, state=11)
        self.assertEqual(response['dungeon_game_state']['buildings'][str(source)]['state'], 11)
        self.call('update_building', building_id=source, state=11)
        self.assign(52, 35)
        self.call('get_dungeon', self.now + 20)
        self.assertEqual(self.session()['participants']['1']['gold_count'], 2)

    def test_nursing_villager_cannot_abandon_baby(self):
        self.data['game_state']['all_villagers']['1']['job']['job_id'] = 3
        old = copy.deepcopy(self.data)
        with self.assertRaises(g.ActionError): self.start()
        self.assertEqual(self.data, old)

    def test_fishing_has_finite_original_stock_and_does_not_refill_on_retry(self):
        self.start(2)
        self.call('get_dungeon', self.now + 420)
        source = self.source(38)
        self.assign(58, 38, at=self.now + 420)
        self.assign(58, 38, at=self.now + 420)
        self.call('get_dungeon', self.now + 470)
        self.assertEqual(self.session()['participants']['1']['gold_count'], 8)
        self.assertEqual(self.session()['participants']['1']['time_worked'], 40)
        self.assertEqual(self.session()['game_state']['buildings'][str(source)]['state'], 1)
        self.assertEqual(self.session()['game_state']['all_villagers']['1']['job']['job_id'], 57)

    def test_drilling_opens_hole_and_role_can_then_fish(self):
        self.start(2)
        self.call('get_dungeon', self.now + 420)
        self.call('set_job', self.now + 420, villager_id=1, job_id=55)
        self.assign(60, 41, at=self.now + 420)
        self.call('get_dungeon', self.now + 480)
        obj = self.session()['game_state']['buildings'][str(self.source(41))]
        self.assertEqual((obj['state'], obj['count']), (21, 5))
        self.assertEqual(self.session()['participants']['1']['gold_count'], 24)
        self.call('set_job', self.now + 480, villager_id=1, job_id=57)
        self.assign(61, 41, at=self.now + 480)
        self.call('get_dungeon', self.now + 530)
        self.assertEqual(self.session()['participants']['1']['gold_count'], 44)

    def test_old_session_claim_cannot_complete_or_change_a_new_session(self):
        self.start()
        old_id = self.session()['id']
        self.call('complete_dungeon_quest', self.now + 330, villager_id=1)
        self.call('start_dungeon', self.now + 400, dungeon_type_id=3, villager_id=1)
        active_id = self.session()['id']
        self.call('complete_dungeon_quest', self.now + 401, villager_id=1, dungeon_id=old_id)
        self.assertEqual(self.data[a.KEY]['active_id'], active_id)
        self.assertTrue(a.is_away(self.data, 1))
        self.assertEqual(self.data['game_state']['points'], 18)

    def test_boost_earned_on_completion_survives_expiry_before_claim(self):
        from apk_revival.meego.engine import effects
        rules = copy.deepcopy(self.rules)
        rules.setdefault('items', {})['1511'] = dict(techtree_id=1511, type=4, target='self',
                                                   activate_count=1, duration=60, bonus_dungeon_reward=50)
        self.data['game_state']['items']['1511'] = dict(item_id=1511, count=1, cooldown=0, last_update=self.now)
        effects.use_item(self.data, 1, 1511, rules, self.now)
        self.start()
        self.assign(62, 42)
        a.advance(self.data, self.now + 60, self.rules)
        effects.advance(self.data, self.now + 60, rules)
        response = self.call('complete_dungeon_quest', self.now + 330, villager_id=1)
        self.assertEqual(response['dungeon_results']['1']['resource_rewards'], {'5': 5})
        self.assertEqual(response['dungeon_results']['1']['bonus_resource_rewards'], {'5': 2})
        self.assertEqual(self.data['game_state']['resources']['5']['count'], 1007)

    def test_no_fabricated_social_lists(self):
        result = self.call('get_dungeons_list')
        self.assertEqual(result, dict(friend_dungeons=[], tribe_dungeons=[], neighbour_dungeons=[]))
        self.assertEqual(self.call('get_active_dungeon'), {'user_dungeon': None})

    def test_offline_large_jump_does_not_farm_idle_cycles(self):
        self.start()
        self.assign(52, 35)
        self.call('get_dungeon', self.now + 100_000_000)
        record = self.session()['participants']['1']
        self.assertEqual(record['gold_count'], 2)
        self.assertEqual(record['time_worked'], 20)

    def test_cyclic_chippers_stop_with_heater_independent_of_polling(self):
        self.start(2)
        self.call('send_villager_to_dungeon', villager_id=2)
        self.assign(53, 36, 1)
        self.assign(54, 37, 2)
        base = copy.deepcopy(self.data)
        self.call('get_dungeon', self.now + 300)
        large = copy.deepcopy(self.session()['participants'])
        self.data = base
        for t in range(1, 301): self.call('get_dungeon', self.now + t)
        self.assertEqual(self.session()['participants'], large)
        self.assertEqual(large['2']['gold_count'], 46)
        self.assertEqual(large['2']['time_worked'], 140)
        self.assertEqual(self.session()['game_state']['all_villagers']['2']['job']['job_id'], 0)


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
class OriginalAdventureTests(AdventureTests):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            tree = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        cls.rules = {key: tree[key] for key in ('dungeon_types', 'dungeon_stages', 'buildings', 'jobs')}


if __name__ == '__main__':
    unittest.main()
