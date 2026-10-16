"""Original-rule integration checks using temporary villages, never live data."""
import copy
import json
import os
from pathlib import Path
import plistlib
import unittest
import zipfile
from unittest.mock import patch

from apk_revival.meego.engine import ecology, effects, local_game as g, server, simulation as sim


def params(**values):
    return {key: [str(value)] for key, value in values.items()}


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires privately owned original APK')
class CoreIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            cls.rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        cls.seed = json.loads((Path(__file__).resolve().parents[3] / 'resources/meego-starter.json').read_text())

    def setUp(self):
        self.rule_patch = patch.object(g, 'RULES', copy.deepcopy(self.rules))
        self.rule_patch.start()
        self.addCleanup(self.rule_patch.stop)
        self.now = 1_000_000
        self.data = server.initial_village(self.seed, self.now, g.RULES)
        ecology.upgrade_bush_stock(self.data)
        self.data = sim.advance(self.data, self.now)

    def test_dungeon_packet_preserves_native_island_identity_and_saved_state(self):
        before = copy.deepcopy(self.data)
        dungeon = copy.deepcopy(self.data['game_state'])
        dungeon.update(name='dungeon', buildings={}, all_villagers={})
        packet = server.native_payload(dict(game_state=self.data['game_state'], dungeon_game_state=dungeon))
        self.assertEqual(packet['game_state']['name'], 'local')
        self.assertEqual(packet['dungeon_game_state']['name'], 'dungeon')
        self.assertEqual(packet['game_state']['buildings'], server.native_payload(self.data['game_state'])['buildings'])
        self.assertEqual(packet['game_state']['all_villagers'], self.data['game_state']['all_villagers'])
        self.assertEqual(self.data, before)

    def test_death_resurrection_and_restart_retain_identity_and_inventory(self):
        data = copy.deepcopy(self.data)
        person = data['game_state']['all_villagers']['1']
        person['deathday'] = self.now + 10
        person['items'] = {'359': {'item_id': 359, 'count': 1}}
        before = copy.deepcopy(person)
        data = sim.advance(data, self.now + 11)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 6)
        data = sim.mutate(data, 'game/village/confirm_dead_villager', params(villager_id=1), self.now + 12)
        person = data['game_state']['all_villagers']['1']
        self.assertEqual(person['job']['job_id'], 0)
        self.assertGreater(person['deathday'], self.now + 12)
        self.assertEqual(person['items'], before['items'])
        self.assertEqual(person['name'], before['name'])
        restored = sim.advance(json.loads(json.dumps(data)), self.now + 13)
        self.assertEqual(restored['game_state']['all_villagers']['1']['job']['job_id'], 0)

    def test_original_turtle_topper_zero_cost_purchase_is_capped_and_preserves_balances(self):
        before = copy.deepcopy(self.data)
        data = sim.mutate(self.data, 'game/purchase/buy_item', params(item_id=371, count=1, use_points='false'), self.now)
        self.assertEqual(data['game_state']['items']['371']['count'], 1)
        self.assertEqual(data['game_state']['resources'], before['game_state']['resources'])
        self.assertEqual(data['game_state']['points'], before['game_state']['points'])
        self.assertEqual(self.data, before)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/purchase/buy_item', params(item_id=371, count=1, use_points='false'), self.now + 1)
        bad_rules = copy.deepcopy(g.RULES)
        del bad_rules['items']['371']['cost']
        with patch.object(g, 'RULES', bad_rules), self.assertRaises(g.ActionError):
            sim.mutate(self.data, 'game/purchase/buy_item', params(item_id=371, count=1, use_points='false'), self.now)

    def test_topper_transfer_clears_native_cached_wearer_and_conserves_ownership(self):
        data = sim.mutate(self.data, 'game/purchase/buy_item', params(item_id=371, count=1, use_points='false'), self.now)
        data = sim.mutate(data, 'game/village/assign_item_to_villager', params(villager_id=1, item_id=371, layer=4), self.now)
        cached = copy.deepcopy(data['game_state']['all_villagers']['1']['items'])
        data = sim.mutate(data, 'game/village/remove_item_from_villager', params(villager_id=1, item_id=371), self.now)
        before = copy.deepcopy(data)
        packet = server.native_payload(data['game_state'])
        self.assertIsNone(packet['all_villagers']['1']['items']['371'])
        # Original strong-dictionary merge deletes explicit null entries;
        # simply sending an empty map leaves cached equipment untouched.
        for key, item in packet['all_villagers']['1']['items'].items():
            if item is None:cached.pop(key, None)
            else:cached[key] = item
        self.assertNotIn('371', cached)
        self.assertEqual(data, before)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/village/remove_item_from_villager', params(villager_id=1, item_id=371), self.now)
        data = sim.mutate(data, 'game/village/assign_item_to_villager', params(villager_id=2, item_id=371, layer=4), self.now)
        data = json.loads(json.dumps(data))
        gs = data['game_state']
        self.assertEqual(gs['items']['371']['count'], 0)
        self.assertNotIn('371', gs['all_villagers']['1']['items'])
        self.assertEqual(gs['all_villagers']['2']['items']['371']['count'], 1)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/village/assign_item_to_villager', params(villager_id=1, item_id=371, layer=4), self.now)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/purchase/buy_item', params(item_id=371, count=1, use_points='false'), self.now)

    def test_storage_zero_housing_accepts_builder_completes_and_increases_caps(self):
        data = copy.deepcopy(self.data)
        data['game_state']['buildings']['9'] = g.building(9, 8, 0, 3845, self.now)
        before_caps = g.caps(data['game_state'])
        self.assertEqual(self.rules['buildings']['8']['state_data']['0']['villager_slots'], 0)
        data = sim.mutate(data, 'game/village/set_job', params(villager_id=1, job_id=5,
                          job_data=json.dumps({'source_id': 9})), self.now)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 5)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/village/set_job', params(villager_id=2, job_id=5,
                       job_data=json.dumps({'source_id': 9})), self.now)
        data = sim.advance(json.loads(json.dumps(data)), self.now + 46)
        self.assertEqual(data['game_state']['buildings']['9']['state'], 1)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)
        after_caps = g.caps(data['game_state'])
        self.assertTrue(all(after_caps[k] > before_caps[k] for k in before_caps))

    def test_thinking_rock_work_progress_and_explicit_unlock_survive_restart(self):
        data = copy.deepcopy(self.data)
        # Original level-two temple and research building; no synthetic recipes.
        data['game_state']['buildings']['1']['state'] = 11
        data['game_state']['buildings']['9'] = g.building(9, 7, 1, 3845, self.now)
        g.synchronize(data, self.now)
        data = sim.mutate(data, 'game/village/set_job', params(villager_id=1, job_id=20,
                          job_data=json.dumps({'source_id': 9})), self.now)
        data = sim.advance(data, self.now + 120)
        points = data['game_state']['resources']['4']['count']
        self.assertGreater(points, 0)
        before = copy.deepcopy(data)
        model = server.catalog.research_progress(data['game_state'], g.RULES)
        self.assertEqual(set(model), {'max_out', 'researching', 'progress'})
        self.assertFalse(model['max_out'])
        self.assertTrue(model['researching'])
        self.assertGreater(model['progress'], 0)
        self.assertLessEqual(model['progress'], 1)
        self.assertEqual(before, data, 'Display polls must not create points or unlocks')
        data['game_state']['resources']['4']['count'] = 30
        data = sim.mutate(data, 'game/purchase/unlock_item', params(item_id=377), self.now + 121)
        self.assertEqual(data['game_state']['resources']['4']['count'], 0)
        self.assertIn('377', server.catalog.researched_items(json.loads(json.dumps(data))['game_state'], g.RULES))
        data = sim.mutate(data, 'game/purchase/unlock_item', params(item_id=377), self.now + 122)
        self.assertEqual(data['game_state']['resources']['4']['count'], 0)

    def test_automatic_discoveries_unlock_original_accessories_and_are_restart_safe(self):
        data = copy.deepcopy(self.data)
        data['game_state']['buildings']['1']['state'] = 31  # Original level-four temple.
        data['game_state']['buildings']['9'] = g.building(9, 7, 1, 3845, self.now)
        g.synchronize(data, self.now)
        data['game_state']['resources']['4']['count'] = 3000
        # Merely opening the UI must neither debit points nor invent items.
        before = copy.deepcopy(data)
        server.catalog.research_progress(data['game_state'], g.RULES)
        self.assertEqual(before, data)
        self.assertEqual(server.catalog.advance_research(data, g.RULES, self.now), [])
        data = sim.mutate(data, 'game/village/set_job', params(villager_id=1, job_id=20,
                          job_data=json.dumps({'source_id': 9})), self.now)
        data = sim.advance(data, self.now + 1)
        unlocked = server.catalog.researched_items(data['game_state'], g.RULES)
        self.assertIn('387', unlocked, 'Original Nose Bone enables Accessories sort_type4')
        self.assertEqual(g.RULES['items']['387']['sort_type'], 4)
        self.assertNotIn('596', unlocked, 'Level-five research must remain gated')
        paid = sum(g.RULES['items'][key]['research_points'] for key in data['local_research_v1']['discoveries'])
        self.assertEqual(data['game_state']['resources']['4']['count'], 3000 - paid)
        self.assertNotIn('387', data['game_state']['items'], 'A discovered recipe is not a free purchased item')
        restored = json.loads(json.dumps(data))
        self.assertEqual(server.catalog.advance_research(restored, g.RULES, self.now + 2), [])
        self.assertEqual(restored, data)
        data['game_state']['all_villagers']['1']['job'] = g.idle_job(self.now + 2)
        data['game_state']['resources']['4']['count'] = 20000
        self.assertEqual(server.catalog.advance_research(data, g.RULES, self.now + 3), [])

    def test_research_upgrade_stops_old_job_and_does_not_create_discoveries(self):
        data = copy.deepcopy(self.data)
        data['game_state']['buildings']['9'] = g.building(9, 7, 1, 3845, self.now)
        data = sim.mutate(data, 'game/village/set_job', params(villager_id=1, job_id=20,
                          job_data=json.dumps({'source_id': 9})), self.now)
        data['game_state']['buildings']['9']['state'] = 10
        data = sim.advance(data, self.now + 120)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)
        self.assertEqual(data['game_state']['resources']['4']['count'], 0)
        self.assertNotIn('local_research_v1', data)

    def test_all_original_temple_upgrades_keep_gates_until_construction_finishes(self):
        data = copy.deepcopy(self.data)
        states = g.RULES['buildings']['1']['state_data']
        for level in range(1, 14):
            with self.subTest(level=level):
                self.assertEqual(data['game_state']['achievements']['102']['level'], level)
                target = states[str(data['game_state']['buildings']['1']['state'])]['valid_transitions'][0]
                target_rule = states[str(target)]
                self.assertTrue(target_rule['buildable'])
                for item, amount in target_rule.get('counter_unit_cost', {}).items():
                    data['game_state']['resources'][str(g.RESOURCE_IDS[int(item)])]['count'] = amount
                data['game_state']['points'] = target_rule.get('points_cost', 0)
                now = self.now + (level - 1) * 50
                data = sim.mutate(data, 'game/village/change_building', params(
                    building_id=1, building_type_id=1, state=target), now)
                self.assertEqual(data['game_state']['achievements']['102']['level'], level)
                data = sim.mutate(data, 'game/village/set_job', params(
                    villager_id=1, job_id=5, job_data=json.dumps({'source_id': 1})), now)
                data = sim.advance(json.loads(json.dumps(data)), now + 46)
                self.assertEqual(data['game_state']['buildings']['1']['state'], target_rule['auto_transition'])
                self.assertEqual(data['game_state']['achievements']['102']['level'], level + 1)
                self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)
                self.assertGreaterEqual(data['game_user']['village_level'], level + 1)
        self.assertEqual(states[str(data['game_state']['buildings']['1']['state'])]['valid_transitions'], [])

    def test_temple_six_to_seven_needs_original_costs_and_cannot_skip_level(self):
        data = copy.deepcopy(self.data)
        data['game_state']['buildings']['1']['state'] = 51
        g.synchronize(data, self.now)
        data['game_state']['resources']['1']['count'] = 90000
        data['game_state']['resources']['2']['count'] = 179999
        data['game_state']['resources']['5']['count'] = 2200
        before = copy.deepcopy(data)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/village/change_building', params(building_id=1, building_type_id=1, state=60), self.now)
        self.assertEqual(data, before)
        data['game_state']['resources']['2']['count'] = 180000
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/village/change_building', params(building_id=1, building_type_id=1, state=70), self.now)
        result = sim.mutate(data, 'game/village/change_building', params(building_id=1, building_type_id=1, state=60), self.now)
        self.assertEqual(result['game_state']['resources']['2']['count'], 0)
        self.assertEqual(result['game_state']['achievements']['102']['level'], 6)
        self.assertEqual(result['game_state']['buildings']['1']['state'], 60)

    def test_village_six_to_seven_affluence_does_not_skip_temple_or_research_gates(self):
        data = copy.deepcopy(self.data)
        data['game_state']['buildings'] = {'1': g.building(1, 1, 51, 200, self.now)}
        data['local_affluence_delta'] = 1969
        g.synchronize(data, self.now)
        info = data['game_state']['village_information']
        self.assertEqual((info['village_level'], info['affluence'], info['next_level_affluence']), (6, 11819, 11820))
        before_resources = copy.deepcopy(data['game_state']['resources'])
        data['local_affluence_delta'] += 1
        g.synchronize(data, self.now + 1)
        self.assertEqual(info['village_level'], 7)
        self.assertEqual(data['game_user']['village_level'], 7)
        self.assertEqual(info['current_level_affluence'], 11820)
        self.assertEqual(info['next_level_affluence'], 13790)
        self.assertEqual(data['game_state']['achievements']['102']['level'], 6)
        self.assertEqual(data['game_state']['buildings']['1']['state'], 51)
        self.assertEqual(data['game_state']['resources'], before_resources)
        with self.assertRaises(g.ActionError):
            g.require_unlocked(data['game_state'], {'unlock_achievement_id': 102, 'unlock_achievement_level': 7})
        restored = json.loads(json.dumps(data))
        g.synchronize(restored, self.now + 2)
        self.assertEqual(restored['game_user']['village_level'], 7)
        self.assertEqual(restored['game_state']['achievements']['102']['level'], 6)

    def source(self, kind, job_id, stock=30):
        data = copy.deepcopy(self.data)
        node = g.building(9, kind, 1, 3845, self.now)
        node['count'] = stock
        data['game_state']['buildings']['9'] = node
        data = sim.mutate(data, 'game/village/set_job', params(
            villager_id=1, job_id=job_id,
            job_data=json.dumps({'source_id': 9, 'destination_id': 1})), self.now)
        return data

    def test_last_unit_all_three_nodes_is_credited_once_and_releases_both_workers(self):
        for kind, job_id, resource in ((2, 16, '1'), (3, 17, '2'), (4, 18, '3')):
            with self.subTest(kind=kind):
                data = self.source(kind, job_id, 1)
                for ident in ('1', '2'):
                    data['game_state']['all_villagers'][ident]['stats']['strength'] = 150
                    data = sim.mutate(data, 'game/village/set_job', params(
                        villager_id=ident, job_id=job_id,
                        job_data=json.dumps({'source_id': 9, 'destination_id': 1})), self.now)
                wire = server.native_payload(data['game_state'])
                self.assertEqual(wire['all_villagers']['1']['job']['gather_rate'], 1)
                self.assertGreater(data['game_state']['all_villagers']['1']['job']['gather_rate'], 1)
                settled = sim.advance(json.loads(json.dumps(data)), self.now + 12)
                self.assertNotIn('9', settled['game_state']['buildings'])
                self.assertIn('9', settled[ecology.REMOVED_KEY])
                packet=server.native_payload(settled['game_state'], depleted_nodes=settled[ecology.REMOVED_KEY])
                self.assertIsNone(packet['buildings']['9'])
                self.assertEqual(settled['game_state']['resources'][resource]['count'], 1)
                self.assertTrue(all(v['job']['job_id'] == 0 for v in settled['game_state']['all_villagers'].values()))
                self.assertEqual(sim.advance(settled, self.now + 12), settled)

    def test_depleted_node_deletions_survive_restart_and_never_remove_reused_or_dungeon_ids(self):
        data=self.source(3,17,1)
        data=sim.advance(data,self.now+12)
        data=json.loads(json.dumps(data))
        before=copy.deepcopy(data)
        self.assertIsNone(server.native_payload(data['game_state'],depleted_nodes=data[ecology.REMOVED_KEY])['buildings']['9'])
        self.assertEqual(data,before)
        data['game_state']['buildings']['9']=g.building(9,5,1,3845,self.now+13)
        packet=server.native_payload(data['game_state'],depleted_nodes=data[ecology.REMOVED_KEY])
        self.assertEqual(packet['buildings']['9']['building_type'],5)
        dungeon=dict(name='dungeon',buildings={},all_villagers={})
        self.assertEqual(server.native_payload(dungeon,depleted_nodes=data[ecology.REMOVED_KEY])['buildings'],{})

    def test_native_baby_dates_are_decimal_and_fixed_deadline_survives_polls_and_growth(self):
        data=copy.deepcopy(self.data)
        people=data['game_state']['all_villagers']
        child=g.villager(3,'Baby',1,[],data['game_user']['user_id'],self.now)
        child.update(birthday=self.now,deathday=self.now+100*3600)
        child['job'].update(job_id=1,target_id=2)
        people['3']=child
        people['2']['job'].update(job_id=3,target_id=3)
        deadline=self.now+2*3600
        for offset in (.2,10.8,120.1,3600.9):
            data=sim.advance(json.loads(json.dumps(data)),self.now+offset)
            before=copy.deepcopy(data)
            packet=json.loads(json.dumps(server.native_payload(data['game_state'])))
            for ident in ('2','3'):
                job=packet['all_villagers'][ident]['job']
                self.assertIs(type(job['last_update']),float)
                self.assertEqual(job['last_update']+job['update_interval'],deadline)
                self.assertLess(job['update_interval'],7201)
            self.assertEqual(data,before)
        data=sim.advance(json.loads(json.dumps(data)),deadline)
        self.assertEqual(data['game_state']['all_villagers']['3']['job']['job_id'],2)
        self.assertEqual(data['game_state']['all_villagers']['2']['job']['job_id'],0)
        data=sim.advance(json.loads(json.dumps(data)),self.now+10*3600)
        self.assertEqual(data['game_state']['all_villagers']['3']['job']['job_id'],0)
        self.assertEqual(data['game_state']['all_villagers']['3']['birthday'],self.now)

    def test_two_resource_base_delivers_two_and_strength_and_tools_still_improve_it(self):
        for kind,job_id,resource in ((2,16,'1'),(3,17,'2'),(4,18,'3')):
            with self.subTest(kind=kind):
                data=self.source(kind,job_id,10)
                person=data['game_state']['all_villagers']['1']
                self.assertEqual(person['job']['gather_rate'],2)
                settled=sim.advance(data,self.now+12)
                self.assertEqual(settled['game_state']['resources'][resource]['count'],2)
                self.assertEqual(settled['game_state']['buildings']['9']['count'],8)
                person['stats']['strength']=110
                self.assertEqual(sim.gather_amount(person,job_id,data,self.now),3)
        self.assertEqual(sim.gather_amount(self.data['game_state']['all_villagers']['1'],20,self.data,self.now),1)

    def test_original_safe_sites_replenish_all_three_kinds_after_json_restart(self):
        data=copy.deepcopy(self.data)
        buildings=data['game_state']['buildings']
        # Fresh seed has only the temple; the native client supplies sites.
        for ident,kind,location in ((2,2,20*g.MAP_SIZE+20),(3,3,30*g.MAP_SIZE+30),(4,4,40*g.MAP_SIZE+40)):
            buildings[str(ident)]=g.building(ident,kind,1,location,self.now)
        ecology.advance(data,self.now+1,rules=g.RULES)
        old_bank=copy.deepcopy(data['game_state']['resources'])
        old_people=copy.deepcopy(data['game_state']['all_villagers'])
        for ident in list(buildings):
            if buildings[ident]['building_type'] in ecology.RESOURCE_LIMITS:
                ecology.remember_depletion(data,buildings[ident],self.now)
                del buildings[ident]
        data[ecology.STATE_KEY]['policy']=ecology.LEGACY_POLICY
        data=json.loads(json.dumps(data))
        when=data[ecology.STATE_KEY]['next_due']
        self.assertIsNotNone(ecology.advance(data,when,rules=g.RULES))
        nodes=[b for b in data['game_state']['buildings'].values() if b['building_type'] in ecology.RESOURCE_LIMITS]
        self.assertEqual(sorted((b['building_type'],b['count']) for b in nodes),[(2,40),(3,30),(4,75)])
        self.assertEqual(data['game_state']['resources'],old_bank)
        self.assertEqual(data['game_state']['all_villagers'],old_people)
        packet=server.native_payload(data['game_state'],depleted_nodes=data[ecology.REMOVED_KEY])
        for node in nodes:self.assertIsNotNone(packet['buildings'][str(node['building_id'])])
        unchanged=copy.deepcopy(data)
        self.assertIsNone(ecology.advance(data,when,rules=g.RULES))
        self.assertEqual(data,unchanged)

    def test_six_node_cap_applies_to_native_spawn_requests_and_timer_without_refills(self):
        for kind in (2,3,4):
            with self.subTest(kind=kind):
                data=copy.deepcopy(self.data)
                for index in range(6):
                    data=g.mutate(data,'game/village/place_resource',params(building_type_id=kind,location=20*g.MAP_SIZE+index*6,orientation=0),self.now)
                buildings=data['game_state']['buildings']
                self.assertEqual(sum(b['building_type']==kind for b in buildings.values()),6)
                before=copy.deepcopy(data)
                rejected=g.mutate(data,'game/village/place_resource',params(building_type_id=kind,location=40*g.MAP_SIZE+40,orientation=0),self.now)
                self.assertEqual(rejected,before)
                ecology.advance(data,self.now+1,rules=g.RULES)
                data[ecology.STATE_KEY]['sites'].append(dict(kind=kind,location=40*g.MAP_SIZE+40,orientation=0))
                bank=copy.deepcopy(data['game_state']['resources'])
                for cycle in range(1,5):
                    ecology.advance(data,self.now+cycle*300+1,rules=g.RULES)
                    self.assertEqual(sum(b['building_type']==kind for b in buildings.values()),6)
                self.assertEqual(data['game_state']['resources'],bank)

    def test_native_move_uses_source_position_then_persists_id_and_orientation(self):
        data=copy.deepcopy(self.data)
        data['game_state']['buildings']['16']=g.building(16,6,1,675,self.now)
        before=copy.deepcopy(data)
        moved=sim.mutate(data,'game/village/move_building',params(building_id=675,to_position=2693,orientation=1),self.now+1)
        self.assertEqual(data,before)
        self.assertEqual(moved['game_state']['buildings']['16']['location'],2693)
        self.assertEqual(moved['game_state']['buildings']['16']['building_id'],16)
        self.assertEqual(moved['game_state']['buildings']['16']['orientation'],1)
        moved=sim.mutate(json.loads(json.dumps(moved)),'game/village/move_building',params(building_id=2693,to_position=2088,orientation=0),self.now+2)
        self.assertEqual(moved['game_state']['buildings']['16']['location'],2088)
        self.assertEqual(moved['game_state']['resources'],before['game_state']['resources'])

    def test_native_move_does_not_allow_overlap_or_unknown_source(self):
        data=copy.deepcopy(self.data)
        data['game_state']['buildings']['16']=g.building(16,6,1,675,self.now)
        before=copy.deepcopy(data)
        for source,destination in ((675,0),(674,2088)):
            with self.assertRaises(g.ActionError):
                sim.mutate(data,'game/village/move_building',params(building_id=source,to_position=destination,orientation=1),self.now+1)
            self.assertEqual(data,before)

    def test_topper_native_absolute_cooldown_and_visible_single_boost_survive_restart(self):
        data=self.source(3,17,30)
        person=data['game_state']['all_villagers']['1']
        person['items']['371']=dict(item_id=371,count=1,layer=4,cooldown=0,last_update=self.now)
        data=sim.mutate(data,'game/village/use_villager_item',params(villager_id=1,item_id=371),self.now)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['gather_rate'],3)
        expected=dict(effect_id=371,expire_date=self.now+180)
        self.assertEqual(data['game_state']['global_state']['effects'],[expected])
        for offset in (0,10,179):
            if offset:data=sim.advance(json.loads(json.dumps(data)),self.now+offset)
            before=copy.deepcopy(data)
            packet=server.native_payload(data['game_state'])
            item=packet['all_villagers']['1']['items']['371']
            self.assertIs(type(item['cooldown']),float)
            self.assertEqual(item['cooldown'],self.now+720)
            self.assertEqual(data,before)
            self.assertEqual(data['game_state']['global_state']['effects'],[expected])
        data=sim.advance(data,self.now+180)
        self.assertEqual(data['game_state']['global_state']['effects'],[])
        with self.assertRaisesRegex(g.ActionError,'cooling down'):
            sim.mutate(data,'game/village/use_villager_item',params(villager_id=1,item_id=371),self.now+719)
        data=sim.advance(data,self.now+720)
        self.assertEqual(server.native_payload(data['game_state'])['all_villagers']['1']['items']['371']['cooldown'],0.0)

    def test_old_active_topper_receipt_gains_indicator_without_reset_or_duplicate(self):
        data=copy.deepcopy(self.data)
        entry=dict(item_id=371,villager_id=1,target='village',started_at=self.now,expires_at=self.now+180)
        data[effects.STATE_KEY]=dict(policy=effects.POLICY,active=[entry],cooldowns={})
        for offset in (1,2):
            effects.advance(data,self.now+offset,g.RULES)
            self.assertEqual(data['game_state']['global_state']['effects'],[dict(effect_id=371,expire_date=self.now+180)])
        effects.advance(data,self.now+180,g.RULES)
        self.assertEqual(data['game_state']['global_state']['effects'],[])

    def test_bush_upgrade_preserves_harvested_food_and_runs_once(self):
        data = self.source(4, 18, 5)
        data['local_migrations'].remove(ecology.BUSH_STOCK_MIGRATION)
        bank = copy.deepcopy(data['game_state']['resources'])
        ecology.upgrade_bush_stock(data)
        self.assertEqual(data['game_state']['buildings']['9']['count'], 60)
        self.assertFalse(ecology.upgrade_bush_stock(data))
        self.assertEqual(data['game_state']['resources'], bank)

    def test_new_bush_has_seventy_five_food(self):
        data = sim.mutate(self.data, 'game/village/place_resource', params(building_type_id=4, location=3845), self.now)
        self.assertEqual(next(b['count'] for b in data['game_state']['buildings'].values() if b['building_type'] == 4), 75)

    def test_three_idle_factories_accept_jobs_finish_then_deplete_to_idle(self):
        for kind, job_id, duration, harvest_job in ((10, 30, 900, 19), (13, 24, 1350, 25), (16, 28, 1080, 29)):
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.data)
                data['game_state']['buildings']['9'] = g.building(9, kind, 1, 3845, self.now)
                data = sim.mutate(data, 'game/village/set_job', params(villager_id=1, job_id=job_id, job_data=json.dumps({'source_id': 9})), self.now)
                self.assertEqual(data['game_state']['buildings']['9']['state'], 11)
                self.assertEqual(data['game_state']['all_villagers']['1']['job']['update_interval'], duration)
                data = sim.advance(data, self.now + duration)
                node = data['game_state']['buildings']['9']
                self.assertEqual(node['state'], 12)
                self.assertGreater(node['count'], 1)
                node['count'] = 1
                data = sim.mutate(data, 'game/village/set_job', params(villager_id=1, job_id=harvest_job, job_data=json.dumps({'source_id': 9, 'destination_id': 1})), self.now + duration)
                data = sim.advance(data, self.now + duration + 12)
                self.assertEqual(data['game_state']['buildings']['9']['state'], 1)
                self.assertEqual(data['game_state']['buildings']['9']['count'], 0)
                self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)

    def test_deleted_or_non_depot_destination_never_receives_a_delivery(self):
        data = self.source(3, 17)
        before = copy.deepcopy(data)
        with self.assertRaises(g.ActionError):
            sim.mutate(data, 'game/village/update_villager_job_destination', params(villager_id=1, destination_id=9), self.now)
        self.assertEqual(data, before)
        data['game_state']['all_villagers']['1']['job']['destination_id'] = 999
        data = sim.advance(data, self.now + 12)
        self.assertEqual(data['game_state']['resources']['2']['count'], 0)
        self.assertEqual(data['game_state']['buildings']['9']['count'], 30)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['job_id'], 0)

    def test_equipping_and_removing_original_chainsaw_updates_active_job(self):
        data = self.source(3, 17)
        baseline = data['game_state']['all_villagers']['1']['job']['gather_rate']
        data['game_state']['items']['1217'] = dict(item_id=1217, count=1, cooldown=0, last_update=self.now)
        equipped = sim.mutate(data, 'game/village/assign_item_to_villager', params(villager_id=1, item_id=1217), self.now)
        self.assertAlmostEqual(equipped['game_state']['all_villagers']['1']['job']['gather_rate'], baseline + 2.32)
        settled = sim.advance(equipped, self.now + 12)
        self.assertEqual(settled['game_state']['resources']['2']['count'], 4)
        removed = sim.mutate(equipped, 'game/village/remove_item_from_villager', params(villager_id=1, item_id=1217), self.now)
        self.assertEqual(removed['game_state']['all_villagers']['1']['job']['gather_rate'], baseline)
        self.assertEqual(removed['game_state']['items']['1217']['count'], 1)

    def test_owned_boost_expires_without_retroactive_or_poll_dependent_yield(self):
        data = self.source(3, 17, 500)
        # Use a synthetic short duration/time modifier to stress a boundary not
        # exercised by the original catalog's one-hour rate-only drinks.
        g.RULES['items']['398'].update(job_ids=[17], job_boost_groups=[], duration=17,
                                     production_time_multiplier=.5)
        data['game_state']['items']['398'] = dict(item_id=398, count=1, cooldown=0, last_update=self.now)
        data = sim.mutate(data, 'game/village/use_villager_item', params(villager_id=1, item_id=398), self.now)
        self.assertEqual(data['game_state']['all_villagers']['1']['job']['trip_time'], 8)
        once = sim.advance(json.loads(json.dumps(data)), self.now + 60)
        polled = data
        for offset in range(1, 61):
            polled = sim.advance(json.loads(json.dumps(polled)), self.now + offset)
        self.assertEqual({k: v['count'] for k, v in once['game_state']['resources'].items()},
                         {k: v['count'] for k, v in polled['game_state']['resources'].items()})
        self.assertEqual(once['game_state']['all_villagers'], polled['game_state']['all_villagers'])
        self.assertEqual(once['game_state']['all_villagers']['1']['job']['trip_time'], 12)


if __name__ == '__main__':
    unittest.main()
