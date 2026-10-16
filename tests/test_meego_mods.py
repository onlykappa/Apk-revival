"""Opt-in task skips against original rules and temporary saves only."""
import copy
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from apk_revival.meego.engine import mods, ecology, effects, local_game as g, server, simulation as sim


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires owned original APK')
class SkipTimerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as archive:
            cls.rules = plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
        cls.seed = json.loads((Path(__file__).resolve().parents[1] / 'resources/meego-starter.json').read_text())

    def setUp(self):
        self.patch = patch.object(g, 'RULES', copy.deepcopy(self.rules))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.now = 1000000
        self.data = sim.advance(server.initial_village(self.seed, self.now, g.RULES), self.now)

    def construction(self, ident=90):
        gs = self.data['game_state']
        gs['buildings'][str(ident)] = g.building(ident, 8, 0, 3845, self.now)
        person = gs['all_villagers'][str(1 if ident == 90 else 2)]
        person['job'].update(job_id=5, source_id=ident, build_rate=1)
        return gs['buildings'][str(ident)]

    def choice(self, kind, ident=None):
        return next(t for t in mods.timers(self.data, self.now)
                    if t['kind'] == kind and (ident is None or t['ident'] == str(ident)))

    def test_list_is_read_only_and_unassigned_construction_not_offered(self):
        self.construction()
        self.data['game_state']['all_villagers']['1']['job'] = g.idle_job(self.now)
        before = copy.deepcopy(self.data)
        self.assertFalse(any(t['kind'] == 'building' for t in mods.timers(self.data, self.now)))
        self.assertEqual(self.data, before)

    def test_finish_only_selected_building_no_skulls_clock_or_other_job_changes(self):
        node = self.construction()
        self.construction(91)
        before = copy.deepcopy(self.data)
        timer = self.choice('building', 90)
        result, _ = mods.skip(self.data, timer['token'], self.now)
        gs = result['game_state']
        self.assertEqual(gs['buildings']['90']['state'], g.RULES['buildings']['8']['state_data']['0']['auto_transition'])
        self.assertEqual(gs['all_villagers']['1']['job']['job_id'], 0)
        self.assertEqual(gs['buildings']['91'], before['game_state']['buildings']['91'])
        self.assertEqual(gs['all_villagers']['2'], before['game_state']['all_villagers']['2'])
        self.assertEqual(gs['resources'], before['game_state']['resources'])
        self.assertEqual(gs['points'], before['game_state']['points'])
        self.assertEqual(result['last_simulated_at'], before['last_simulated_at'])
        self.assertEqual(self.data, before)
        self.assertEqual(len(result['local_mod_history']), 1)
        with self.assertRaises(g.ActionError):mods.skip(result, timer['token'], self.now)

    def test_token_survives_normal_progress_but_rejects_changed_task(self):
        node = self.construction()
        timer = self.choice('building', 90)
        node['progress'] += 0.5
        self.assertEqual(self.choice('building', 90)['token'], timer['token'])
        self.data['game_state']['all_villagers']['1']['job']['job_start_date'] += 1
        with self.assertRaises(g.ActionError):mods.skip(self.data, timer['token'], self.now)
        node['state'] = 1
        with self.assertRaises(g.ActionError):mods.skip(self.data, timer['token'], self.now)

    def test_stocking_finishes_once_with_original_stock_and_idle_worker(self):
        kind = 10
        state, rule = next((int(k), r) for k, r in g.RULES['buildings'][str(kind)]['state_data'].items() if r.get('stocking_phase'))
        node = g.building(90, kind, state, 3845, self.now)
        node['local_production_cycle'] = 2
        self.data['game_state']['buildings']['90'] = node
        self.data['game_state']['all_villagers']['1']['job'].update(job_id=rule['active_job'], source_id=90)
        timer = self.choice('building', 90)
        result, _ = mods.skip(self.data, timer['token'], self.now)
        output = result['game_state']['buildings']['90']
        expected = g.RULES['buildings'][str(kind)]['state_data'][str(rule['auto_transition'])]
        self.assertEqual(output['count'], expected['default_length'])
        self.assertEqual(output['state'], rule['auto_transition'])
        self.assertEqual(result['game_state']['all_villagers']['1']['job']['job_id'], 0)
        with self.assertRaises(g.ActionError):mods.skip(result, timer['token'], self.now)
        node['local_production_cycle'] = 3
        with self.assertRaises(g.ActionError):mods.skip(self.data, timer['token'], self.now)

    def test_growth_one_stage_and_releases_parent_without_aging_other_people(self):
        people = self.data['game_state']['all_villagers']
        baby = people['1']
        baby['birthday'] = self.now - 3600
        baby['job']['job_id'] = 1
        people['2']['job'].update(job_id=3, target_id=1)
        people['3'] = g.villager(3, 'Other', 1, [], 1, self.now)
        other = copy.deepcopy(people['3'])
        deathday = baby['deathday']
        token = self.choice('growth', 1)['token']
        result, _ = mods.skip(self.data, token, self.now)
        child = result['game_state']['all_villagers']['1']
        self.assertEqual(child['job']['job_id'], 2)
        self.assertEqual(child['deathday'], deathday)
        self.assertEqual(result['game_state']['all_villagers']['2']['job']['job_id'], 0)
        self.assertEqual(result['game_state']['all_villagers']['3'], other)
        with self.assertRaises(g.ActionError):mods.skip(result, token, self.now)
        token = next(t['token'] for t in mods.timers(result, self.now) if t['kind'] == 'growth')
        adult, _ = mods.skip(result, token, self.now)
        self.assertEqual(adult['game_state']['all_villagers']['1']['job']['job_id'], 0)

    def test_cooldown_preserves_item_ownership(self):
        item = dict(item_id=371, count=1, cooldown=720, last_update=self.now)
        self.data['game_state']['items']['371'] = item
        self.data[effects.STATE_KEY] = dict(policy=effects.POLICY, active=[], cooldowns={
            'village:371': dict(owner='village', item_id=371, ready_at=self.now + 720)})
        result, _ = mods.skip(self.data, self.choice('cooldown')['token'], self.now)
        self.assertEqual(result['game_state']['items']['371']['cooldown'], 0)
        self.assertEqual(result['game_state']['items']['371']['count'], 1)
        self.assertEqual(result[effects.STATE_KEY]['cooldowns'], {})
        self.assertEqual(self.data['game_state']['items']['371']['cooldown'], 720)

    def test_cooldown_skip_does_not_restart_or_remove_active_topper_buff(self):
        self.data['game_state']['items']['371'] = dict(item_id=371, count=1, cooldown=0, last_update=self.now)
        effects.use_item(self.data, 1, 371, g.RULES, self.now)
        active = copy.deepcopy(self.data[effects.STATE_KEY]['active'])
        result, _ = mods.skip(self.data, self.choice('cooldown')['token'], self.now)
        self.assertEqual(result[effects.STATE_KEY]['active'], active)
        self.assertEqual(result['game_state']['items']['371']['count'], 1)

    def test_class_completes_once_and_leaves_normal_report_collection(self):
        states = g.RULES['buildings']['30']['state_data']
        active, rule = next((int(k), r) for k, r in states.items() if r.get('active_job') == 46)
        gs = self.data['game_state']
        gs['buildings']['90'] = g.building(90, 30, active, 3845, self.now)
        gs['all_villagers']['1']['job'].update(job_id=46, source_id=90)
        child = gs['all_villagers']['2']
        child['birthday'] = self.now - 3 * 3600
        child['job'].update(job_id=47, source_id=90)
        initial = child['stats']['intelligence']
        self.data['school_sessions'] = {'90': dict(teacher_id=1, student_ids=[2], started_at=self.now,
            ends_at=self.now + 3600, active_state=active, idle_state=rule['auto_transition'])}
        token = self.choice('school')['token']
        result, _ = mods.skip(self.data, token, self.now)
        self.assertEqual(result['school_sessions'], {})
        self.assertEqual(result['game_state']['all_villagers']['2']['job']['job_id'], 48)
        self.assertEqual(result['game_state']['all_villagers']['2']['stats']['intelligence'], initial + 1)
        self.assertIn('2', result['school_reports']['90'])
        with self.assertRaises(g.ActionError):mods.skip(result, token, self.now)

    def test_respawn_uses_normal_caps_and_does_not_mint_bank_balances(self):
        gs = self.data['game_state']
        node = g.building(90, 3, 1, 3845, self.now)
        node['count'] = 30
        gs['buildings']['90'] = node
        ecology.advance(self.data, self.now + 1, rules=g.RULES)
        self.now += 2
        kind = node['building_type']
        ecology.remember_depletion(self.data, node, self.now)
        del gs['buildings'][str(node['building_id'])]
        timer = self.choice('respawn')
        result, _ = mods.skip(self.data, timer['token'], self.now)
        self.assertEqual(result['game_state']['resources'], gs['resources'])
        self.assertGreater(sum(b['building_type'] == kind for b in result['game_state']['buildings'].values()), sum(b['building_type'] == kind for b in gs['buildings'].values()))
        for kind, cap in ecology.RESOURCE_LIMITS.items():
            self.assertLessEqual(sum(b['building_type'] == kind for b in result['game_state']['buildings'].values()), cap)
        with self.assertRaises(g.ActionError):mods.skip(result, timer['token'], self.now)

    def test_atomic_state_skip_persists_and_restart_does_not_replay(self):
        self.construction()
        with tempfile.TemporaryDirectory() as folder, patch.object(server.time, 'time', return_value=self.now):
            server.atomic_json(Path(folder) / 'saves/village.json', self.data)
            state = server.State(folder, self.seed)
            before = state.save.read_bytes()
            timer = next(t for t in state.mod_timers() if t['kind'] == 'building')
            self.assertEqual(state.save.read_bytes(), before)
            state.skip_timer(timer['token'])
            saved = state.save.read_bytes()
            restarted = server.State(folder, self.seed)
            with self.assertRaises(g.ActionError):restarted.skip_timer(timer['token'])
            self.assertEqual(restarted.save.read_bytes(), saved)
            self.assertTrue(list((Path(folder) / 'backups').glob('village-*.json')))
