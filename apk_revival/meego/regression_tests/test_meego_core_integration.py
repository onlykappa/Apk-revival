"""Original-rule integration checks using temporary villages, never live data."""
import copy
import json
import os
from pathlib import Path
import plistlib
import unittest
import zipfile
from unittest.mock import patch

from apk_revival.meego.engine import ecology, local_game as g, server, simulation as sim


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
                self.assertEqual(settled['game_state']['resources'][resource]['count'], 1)
                self.assertTrue(all(v['job']['job_id'] == 0 for v in settled['game_state']['all_villagers'].values()))
                self.assertEqual(sim.advance(settled, self.now + 12), settled)

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
        self.assertEqual(settled['game_state']['resources']['2']['count'], 3)
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
