"""Real request parsing and persistent reward accounting, without sockets."""
import base64
import copy
import hmac
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile

from apk_revival.meego.engine import local_game as g, server


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
class SoloWireIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        self.rules_patch = patch.object(g, 'RULES', rules)
        self.rules_patch.start()
        self.addCleanup(self.rules_patch.stop)
        self.now = 1_000_000
        self.clock = patch('apk_revival.meego.engine.server.time.time', side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        seed = json.loads((Path(__file__).resolve().parents[3] / 'resources/meego-starter.json').read_text())
        self.state = server.State(self.temp.name, seed)

    def request(self, route, values=None, raw=None, content_type='application/x-www-form-urlencoded'):
        body = raw if raw is not None else urlencode(values or {}).encode()
        state = self.state
        class Capture(server.Handler):
            def __init__(inner):
                inner.path = '/' + route
                inner.client_address = ('127.0.0.1', 12345)
                inner.headers = {'Content-Length': str(len(body)), 'Content-Type': content_type}
                inner.rfile = io.BytesIO(body)
                inner.server = SimpleNamespace(state=state)
            def reply(inner, code, value):
                inner.result = (code, server.native_payload(value, state.data['game_state']))
        handler = Capture()
        handler.dispatch()
        return handler.result

    def treasure(self):
        code, model = self.request('game/village/get_treasure_mini_game', {'minigame_type': 1})
        self.assertEqual(code, 200)
        self.assertFalse(model['new_session'])
        self.now += 3600
        code, model = self.request('game/village/get_treasure_mini_game', {'minigame_type': 1})
        self.assertEqual(code, 200)
        self.assertTrue(model['new_session'])
        return model

    def signed(self, model):
        payload = {'payout_number': 1, 'token': model['token'], 'minigame_type': 1}
        raw = json.dumps(payload, separators=(',', ':'))
        signature = base64.b64encode(hmac.digest(model['token'].encode(), raw.encode(), 'sha256')).decode()
        return payload, raw, signature

    def test_native_form_reward_restart_and_retry_never_duplicate(self):
        model = self.treasure()
        payload, raw, signature = self.signed(model)
        before = self.state.data['game_state']['points']
        args = dict(data=raw, signature=signature)
        code, response = self.request('game/village/retrieve_treasure_mini_game_reward', args)
        self.assertEqual(code, 200)
        self.assertEqual(response['points_reward'], 1)
        self.assertEqual(response['game_state']['points'], before + 1)
        self.state = server.State(self.temp.name, self.state.seed)
        code, retry = self.request('game/village/retrieve_treasure_mini_game_reward', args)
        self.assertEqual(code, 200)
        self.assertEqual(retry['points_reward'], 0)
        self.assertEqual(retry['game_state']['points'], before + 1)
        logs = self.state.logfile.read_text()
        self.assertNotIn(model['token'], logs)
        self.assertNotIn(signature, logs)

    def test_nested_json_envelope_is_not_converted_to_python_dict_text(self):
        model = self.treasure()
        payload, raw, signature = self.signed(model)
        body = json.dumps(dict(data=payload, signature=signature)).encode()
        code, response = self.request('game/village/retrieve_treasure_mini_game_reward',
                                      raw=body, content_type='application/json')
        self.assertEqual(code, 200)
        self.assertEqual(response['points_reward'], 1)

    def test_duplicate_json_keys_and_invalid_signature_leave_balances_intact(self):
        model = self.treasure()
        payload, raw, signature = self.signed(model)
        before = copy.deepcopy(self.state.data)
        body = ('{"data":' + raw + ',"signature":"x","signature":"' + signature + '"}').encode()
        self.assertEqual(self.request('game/village/retrieve_treasure_mini_game_reward',
                                     raw=body, content_type='application/json')[0], 400)
        self.assertEqual(self.state.data, before)
        self.assertEqual(self.request('game/village/retrieve_treasure_mini_game_reward',
                                     dict(data=raw, signature='x'))[0], 409)
        self.assertEqual(self.state.data['game_state']['points'], before['game_state']['points'])

    def test_rejected_repeated_data_fields_do_not_leak_tokens_to_logs(self):
        model = self.treasure()
        payload, raw, signature = self.signed(model)
        body = urlencode([('data', raw), ('data', raw), ('signature', signature)]).encode()
        code, response = self.request('game/village/retrieve_treasure_mini_game_reward', raw=body)
        self.assertEqual(code, 409)
        self.assertNotIn(model['token'], self.state.logfile.read_text())
        self.assertNotIn(signature, self.state.logfile.read_text())

    def test_paid_commercial_work_only_reaches_inventory_when_collected(self):
        data = copy.deepcopy(self.state.data)
        data['game_state']['resources']['3']['count'] = 5000  # Temporary funded fixture only.
        data['game_state']['buildings']['9'] = g.building(9, 11, 1, 3845, self.now)
        self.state.persist(data)
        code, response = self.request('game/village/set_job', dict(villager_id=1, job_id=21,
            job_data=json.dumps(dict(source_id=9, building_type_id=11, state=1))))
        self.assertEqual(code, 200)
        self.assertEqual(response['buildings']['9']['expire_date'], self.now + 3600)
        self.now += 3600
        with patch('apk_revival.meego.engine.commercial._roll', return_value=0):
            code, response = self.request('game/village/get_resources')
        self.assertEqual(response['buildings']['9']['items']['398']['count'], 1)
        self.assertEqual(response['items'].get('398', {}).get('count', 0), 0)
        code, response = self.request('game/village/collect_building_items', dict(building_type_id=11, location=3845))
        self.assertEqual(code, 200)
        self.assertEqual(response['items']['398']['count'], 1)
        self.assertEqual(response['buildings']['9']['items'], {})
        code, retry = self.request('game/village/collect_building_items', dict(building_type_id=11, location=3845))
        self.assertEqual(retry['items']['398']['count'], 1)

    def test_native_portal_departure_work_restart_return_and_boosted_claim(self):
        data = copy.deepcopy(self.state.data)
        data['game_state']['points'] = 10  # Fund only the temporary test village.
        data['game_state']['buildings']['9'] = g.building(9, 34, 1, 3845, self.now)
        data['game_state']['items']['1511'] = dict(item_id=1511, count=1, cooldown=0, last_update=self.now)
        self.state.persist(data)
        self.assertEqual(self.request('game/village/set_job', dict(villager_id=1, job_id=49,
                        job_data=json.dumps(dict(source_id=9))))[0], 200)
        self.assertEqual(self.request('game/village/use_villager_item', dict(villager_id=1, item_id=1511))[0], 200)
        code, packet = self.request('game/dungeon/start_dungeon', dict(dungeon_type_id=3, villager_id=1))
        self.assertEqual(code, 200)
        self.assertIn('dungeon_game_state', packet)
        ident = packet['user_dungeon']['dungeon_id']
        self.assertEqual(packet['game_state']['all_villagers']['1']['location_type'], 1)
        self.assertEqual(packet['game_state']['points'], 9)
        pump = next(b for b in packet['dungeon_game_state']['buildings'].values() if b['building_type'] == 35)
        self.assertEqual(self.request('game/dungeon/set_job', dict(dungeon_id=ident, villager_id=1,
                        job_id=52, job_data=json.dumps(dict(source_id=pump['building_id'],
                            building_type_id=35, source_worker_ids=[], state=11))))[0], 200)
        self.now += 20
        code, island = self.request('game/village/get_resources')
        self.assertEqual(code, 200)
        self.assertEqual(island['resources']['5']['count'], 0, 'Work remains staged until results claim')
        for route, values in (
            ('game/village/set_job', dict(villager_id=1, job_id=0)),
            ('game/village/change_villager_name', dict(villager_id=1, villager_name='Overwrite')),
            ('game/village/use_villager_item', dict(villager_id=1, item_id=1511)),
        ):
            self.assertEqual(self.request(route, values)[0], 409)
        self.state = server.State(self.temp.name, self.state.seed)
        self.now += 310
        code, result = self.request('game/dungeon/complete_dungeon_quest', dict(villager_id=1))
        self.assertEqual(code, 200)
        self.assertEqual(result['dungeon_results']['1']['resource_rewards']['5'], 2)
        self.assertEqual(result['dungeon_results']['1']['bonus_resource_rewards']['5'], 1)
        self.assertEqual(result['game_state']['resources']['5']['count'], 3)
        self.assertEqual(result['game_state']['all_villagers']['1']['location_type'], 0)
        self.assertEqual(result['game_state']['all_villagers']['1']['job']['job_id'], 0)
        self.assertEqual(result['game_state']['points'], 9)
        code, retry = self.request('game/dungeon/complete_dungeon_quest', dict(villager_id=1))
        self.assertEqual(code, 200)
        self.assertEqual(retry['game_state']['resources']['5']['count'], 3)

    def test_dungeon_loot_count_map_matches_inventory_and_never_repeats_on_claim(self):
        data = copy.deepcopy(self.state.data)
        data['game_state']['points'] = 10
        data['game_state']['buildings']['9'] = g.building(9, 34, 1, 3845, self.now)
        self.state.persist(data)
        code, packet = self.request('game/dungeon/start_dungeon', dict(dungeon_type_id=3, villager_id=1))
        self.assertEqual(code, 200)
        ident = packet['user_dungeon']['dungeon_id']
        pump = next(b for b in packet['dungeon_game_state']['buildings'].values() if b['building_type'] == 35)
        for _ in range(3):
            self.assertEqual(self.request('game/dungeon/set_job', dict(dungeon_id=ident,
                villager_id=1, job_id=52, job_data=json.dumps(dict(source_id=pump['building_id'],
                    building_type_id=35, source_worker_ids=[], state=11))))[0], 200)
            self.now += 20
        self.now += 270
        code, result = self.request('game/dungeon/complete_dungeon_quest', dict(villager_id=1))
        self.assertEqual(code, 200)
        loot = result['dungeon_results']['1']['item_rewards']
        self.assertEqual(len(loot), 1)
        item_id = next(iter(loot))
        self.assertEqual(loot[item_id], 1)
        self.assertEqual(result['game_state']['items'][item_id]['count'], 1)
        self.assertEqual(result['dungeon_summary']['1']['quest_results']['items'], loot)
        code, retry = self.request('game/dungeon/complete_dungeon_quest', dict(villager_id=1))
        self.assertEqual(code, 200)
        self.assertEqual(retry['game_state']['items'][item_id]['count'], 1)

    def test_owned_scripted_box_opens_through_actual_native_gift_route(self):
        data = copy.deepcopy(self.state.data)
        data['game_state']['gifts'] = {'42': dict(gift_id=42, gift_type=3, gift_item_id=1177,
            gift_count=1, from_user_id=7, from_username='Local', message='', date_sent=self.now)}
        people = copy.deepcopy(data['game_state']['all_villagers'])
        self.state.persist(data)
        code, response = self.request('game/gift/open_gift', dict(gift_id=42, villager_ids='[]'))
        self.assertEqual(code, 200)
        self.assertEqual(response['game_state']['gifts'], {})
        self.assertEqual(response['game_state']['all_villagers'], people)
        self.assertEqual(self.request('game/gift/open_gift', dict(gift_id=42, villager_ids='[]'))[0], 409)


if __name__ == '__main__':
    unittest.main()
