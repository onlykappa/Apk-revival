"""Treasure transport/economy checks using synthetic saves only."""
import base64
import copy
import hmac
import itertools
import json
import os
import plistlib
import unittest
import zipfile

from apk_revival.meego.engine import treasure as t, local_game as g


class TreasureTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000
        self.data = {'game_state': {'points': 7, 'items': {}}, 'game_user': {'user_id': 1}}
        self.rules = {'client_data': {'8': {'mini_game_details_1': {
            'idle_duration': 60, 'game_duration': 30, 'reward_duration': 60}}}}

    def open_session(self):
        data, first = t.poll(self.data, {}, self.rules, self.now)
        self.assertFalse(first['new_session'])
        return t.poll(data, {}, self.rules, self.now + 3600)

    def request(self, model, payout=1, order=t.KEYS):
        payload = {'payout_number': payout, 'token': model['token'], 'minigame_type': 1}
        raw = json.dumps({k: payload[k] for k in order}, separators=(',', ':'))
        signature = base64.b64encode(hmac.digest(model['token'].encode(), raw.encode(), 'sha256')).decode()
        return {'data': [raw], 'signature': [signature]}

    def test_initial_poll_grants_nothing_and_preserves_input(self):
        before = copy.deepcopy(self.data)
        new, model = t.poll(self.data, {}, self.rules, self.now)
        self.assertEqual(self.data, before)
        self.assertEqual(new['game_state'], self.data['game_state'])
        self.assertFalse(model['new_session'])
        self.assertEqual(model['next_poll_date'], self.now + 3600)

    def test_direct_model_native_fields_and_duration(self):
        data, model = self.open_session()
        self.assertTrue(model['new_session'])
        self.assertEqual(model['minigame_type'], 1)
        self.assertEqual(model['level'], 1)
        self.assertGreater(model['expire_date'] - model['start_date'], 150)
        self.assertEqual(len(model['token']), 48)
        self.assertNotIn('game_state', model)
        self.assertEqual(data['game_state']['points'], 7)

    def test_repeat_poll_restart_does_not_retrigger_or_replace_token(self):
        data, model = self.open_session()
        restored = json.loads(json.dumps(data))
        new, repeated = t.poll(restored, {}, self.rules, self.now + 3601)
        self.assertFalse(repeated['new_session'])
        self.assertEqual(repeated['token'], model['token'])
        self.assertEqual(new, restored)

    def test_reward_is_atomic_one_skull_no_items(self):
        data, model = self.open_session()
        before = copy.deepcopy(data)
        new, reward = t.retrieve(data, self.request(model), self.rules, self.now + 3670)
        self.assertEqual(data, before)
        self.assertEqual(new['game_state']['points'], 8)
        self.assertEqual(reward['points_reward'], 1)
        self.assertEqual(reward['item_rewards'], {})
        self.assertEqual(reward['game_state'], new['game_state'])

    def test_signed_exact_retry_does_not_double_award_after_restart(self):
        data, model = self.open_session()
        new, _ = t.retrieve(data, self.request(model), self.rules, self.now + 3670)
        new = json.loads(json.dumps(new))
        repeated, reward = t.retrieve(new, self.request(model), self.rules, self.now + 3671)
        self.assertEqual(repeated, new)
        self.assertEqual(reward['points_reward'], 0)

    def test_different_payout_cannot_claim_second_session_reward(self):
        data, model = self.open_session()
        new, _ = t.retrieve(data, self.request(model), self.rules, self.now + 3670)
        with self.assertRaises(g.ActionError):
            t.retrieve(new, self.request(model, 2), self.rules, self.now + 3671)

    def test_all_six_native_dictionary_orders_validate(self):
        data, model = self.open_session()
        for order in itertools.permutations(t.KEYS):
            with self.subTest(order=order):
                _, reward = t.retrieve(data, self.request(model, order=order), self.rules, self.now + 3670)
                self.assertEqual(reward['points_reward'], 1)

    def test_missing_corrupt_or_sha1_signature_rejected(self):
        data, model = self.open_session()
        for signature in ('', 'A' * 44, '!', base64.b64encode(b'x' * 20).decode()):
            request = self.request(model)
            request['signature'] = [signature]
            with self.assertRaises(g.ActionError):
                t.retrieve(data, request, self.rules, self.now + 3670)

    def test_payload_tampering_and_unknown_fields_rejected(self):
        data, model = self.open_session()
        request = self.request(model)
        value = json.loads(request['data'][0]); value['payout_number'] = 2
        request['data'] = [json.dumps(value)]
        with self.assertRaises(g.ActionError):
            t.retrieve(data, request, self.rules, self.now + 3670)
        value['points_reward'] = 10000
        request['data'] = [json.dumps(value)]
        with self.assertRaises(g.ActionError):
            t.retrieve(data, request, self.rules, self.now + 3670)

    def test_duplicate_keys_boolean_and_out_of_range_rejected(self):
        data, model = self.open_session()
        for raw in ('{"payout_number":1,"payout_number":2}',
                    '{"payout_number":true,"token":"' + model['token'] + '","minigame_type":1}'):
            with self.assertRaises(g.ActionError):
                t.retrieve(data, {'data': [raw], 'signature': ['x']}, self.rules, self.now + 3670)
        for number in (-1, 6):
            with self.assertRaises(g.ActionError):
                t.retrieve(data, self.request(model, number), self.rules, self.now + 3670)

    def test_expiry_boundary_and_earlier_clock_reject_without_mutation(self):
        data, model = self.open_session()
        before = copy.deepcopy(data)
        for now in (model['start_date'] - 1, model['expire_date'], model['expire_date'] + 1):
            with self.assertRaises(g.ActionError):
                t.retrieve(data, self.request(model), self.rules, now)
        self.assertEqual(data, before)

    def test_long_offline_gap_grants_one_opportunity_and_no_catchup(self):
        data, _ = t.poll(self.data, {}, self.rules, self.now)
        far = self.now + 30 * 86400
        data, model = t.poll(data, {}, self.rules, far)
        self.assertTrue(model['new_session'])
        self.assertEqual(model['next_poll_date'], far + 3600)
        for now in (far + 156, far + 3599):
            data, model = t.poll(data, {}, self.rules, now)
            self.assertFalse(model['new_session'])
        self.assertEqual(data['game_state']['points'], 7)

    def test_old_token_after_new_opportunity_rejected(self):
        data, old = self.open_session()
        data, model = t.poll(data, {}, self.rules, self.now + 7200)
        self.assertNotEqual(old['token'], model['token'])
        with self.assertRaises(g.ActionError):
            t.retrieve(data, self.request(old), self.rules, self.now + 7270)

    def test_invalid_type_clock_or_missing_rules_reject(self):
        for params, rules, now in (({'minigame_type': ['2']}, self.rules, self.now),
                                   ({}, {}, self.now), ({}, self.rules, float('nan'))):
            with self.assertRaises(g.ActionError):
                t.poll(self.data, params, rules, now)

    @unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
    def test_original_apk_timing_is_compatible(self):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            tree = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        _, model = t.poll(self.data, {}, {'client_data': tree['client_data']}, self.now)
        self.assertEqual(model['minigame_type'], 1)
