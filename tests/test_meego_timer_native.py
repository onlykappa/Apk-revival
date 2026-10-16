"""Original-asset and native callback regressions; no live village mutation."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from apk_revival.meego import ccb, camera, timer_mod
from apk_revival.meego.adapter import MeegoAdapter, ORIGINAL_SHA
from apk_revival.meego.engine import local_game as g, server
from apk_revival.util import RevivalError
import test_meego_mods as fixtures


@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires owned original APK')
class NativeTimerAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(os.environ['APKR_MEEGO_APK']) as z:
            cls.panel=z.read(timer_mod.ASSET);cls.library=z.read('lib/armeabi/libverde.so')

    def walk(self,node):
        yield node
        for child in node['children']:yield from self.walk(child)

    def test_original_panel_roundtrips_exactly_and_unreviewed_panels_reject(self):
        reader=ccb.Reader(self.panel)
        self.assertEqual(reader.dump(reader.read()), self.panel)
        with self.assertRaises(RevivalError):timer_mod.patched_panel(self.panel+b'x')

    def test_skip_reuses_bound_completion_button_beside_close_without_overlap(self):
        result=timer_mod.patched_panel(self.panel)
        reader=ccb.Reader(result);root=reader.read()
        self.assertEqual(reader.dump(root),result)
        nodes=list(self.walk(root))
        buttons=[n for n in nodes if n['name']=='completeSkullsButton']
        self.assertEqual(len(buttons),1)
        menu=next(n for n in nodes if buttons[0] in n['children'])
        self.assertEqual(menu['cls'],'CCMenu')
        def props(n):return {p['name']:p['value'] for p in n['props']}
        close=next(n for n in menu['children'] if props(n).get('block')==('onClose',2))
        skip=props(buttons[0]);self.assertEqual(skip['block'],('onCompleteSkulls',2))
        self.assertLess(skip['position'][0]+103*skip['scale'][0]/2,
                        props(close)['position'][0]-43/2)
        labels=[n for n in root['children'] if props(n).get('string')=='Skip timer']
        self.assertEqual(len(labels),1);self.assertEqual(labels[0]['assignment'],0)
        self.assertTrue(any(n['name']=='anchorSkullsPanel' for n in nodes))

    def test_native_patches_have_exact_preconditions_and_preserve_library_length(self):
        patches=timer_mod.native_patches(self.library);self.assertEqual(len(patches),7)
        changed=bytearray(self.library)
        for p in patches:
            old=bytes.fromhex(p['old']);new=bytes.fromhex(p['new']);off=p['offset']
            self.assertEqual(changed[off:off+len(old)],old)
            self.assertEqual(len(old),len(new));changed[off:off+len(old)]=new
        self.assertEqual(len(changed),len(self.library))
        with self.assertRaises(RevivalError):timer_mod.native_patches(changed)

    def test_plan_contains_ui_and_backend_revision_and_old_client_needs_upgrade(self):
        store=Mock();store.base.return_value=Path(os.environ['APKR_MEEGO_APK'])
        p=dict(apk_sha256=ORIGINAL_SHA,apk_version={'name':'1.32','code':1},runtime={'backend_port':18765})
        plan=MeegoAdapter().plan(store,p,'local_backend')
        self.assertEqual(plan['meego_client_fixes']['native_timer_mod'],1)
        op=next(o for o in plan['operations'] if o['file']==timer_mod.ASSET)
        self.assertEqual(op['type'],'meego_timer_panel')
        self.assertEqual(op['expected_sha256'],timer_mod.ASSET_SHA)
        self.assertFalse(camera.prepared({'plan':{'meego_client_fixes':{'revision':1,'timer_hz':60}}}))

    def test_panel_operation_rejects_unreviewed_asset_revision_and_hash(self):
        from apk_revival.restoration import Restorer
        store=Mock();store.base.return_value=Path(os.environ['APKR_MEEGO_APK'])
        p=dict(adapter='meego-1.32',apk_sha256=ORIGINAL_SHA,apk_version={'name':'1.32','code':1},runtime={'backend_port':18765})
        plan=MeegoAdapter().plan(store,p,'local_backend')
        Restorer(store)._validate(p,plan,'local_backend')
        for field,value in (('file','assets/Other.ccbi'),('revision',2),('expected_sha256','0'*64)):
            bad=copy.deepcopy(plan);op=next(o for o in bad['operations'] if o['type']=='meego_timer_panel');op[field]=value
            with self.assertRaises(RevivalError):Restorer(store)._validate(p,bad,'local_backend')

    def test_busy_game_snapshot_is_bounded_instead_of_blocking_ui(self):
        state=server.State.__new__(server.State);state.lock=Mock();state.lock.acquire.return_value=False
        with self.assertRaisesRegex(g.ActionError,'Game is updating'):state.mod_timers()
        state.lock.acquire.assert_called_once_with(timeout=0.05)



@unittest.skipUnless(os.environ.get('APKR_MEEGO_APK'), 'Requires owned original APK')
class NativeTimerCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SkipTimerTests.setUpClass();cls.rules=fixtures.SkipTimerTests.rules;cls.seed=fixtures.SkipTimerTests.seed

    def setUp(self):
        self.now=1000000
        self.patch=patch.object(g,'RULES',copy.deepcopy(self.rules));self.patch.start();self.addCleanup(self.patch.stop)
        self.clock=patch.object(server.time,'time',return_value=self.now);self.clock.start();self.addCleanup(self.clock.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=server.State(self.temp.name,self.seed)
        self.state.native_timer_mod=True
        gs=self.state.data['game_state']
        baby=gs['all_villagers']['1'];baby.update(birthday=self.now-100,job=g.idle_job(self.now));baby['job'].update(job_id=1,target_id=2)
        gs['all_villagers']['2']['job'].update(job_id=3,target_id=1)
        gs['points']=0
        self.state.persist(self.state.data)

    def request(self,route,**kw):return self.state.handle(route,{k:[str(v)] for k,v in kw.items()})

    def test_native_parent_and_child_callbacks_free_persisted_and_retry_safe(self):
        result,status=self.request('game/points/speed_up_parenting',villager_id=2,baby_id=1,expected_cost=0)
        self.assertEqual(status,'local-mod-skip-timer')
        self.assertEqual(result['all_villagers']['1']['job']['job_id'],2)
        self.assertEqual(result['all_villagers']['2']['job']['job_id'],0)
        self.assertEqual(result['points'],0)
        _,status=self.request('game/points/speed_up_parenting',villager_id=2,baby_id=1,expected_cost=0)
        self.assertEqual(status,'rejected-local-action')
        result,status=self.request('game/points/speed_up_child_aging',villager_id=1,expected_cost=0)
        self.assertEqual(status,'local-mod-skip-timer');self.assertEqual(result['all_villagers']['1']['job']['job_id'],0)
        self.assertEqual(result['points'],0)
        restarted=server.State(self.temp.name,self.seed)
        self.assertEqual(len(restarted.data['local_mod_history']),2)

    def test_existing_unmodded_client_keeps_original_paid_path(self):
        self.state.native_timer_mod=False
        result,status=self.request('game/points/speed_up_parenting',villager_id=2,baby_id=1,expected_cost=0)
        self.assertEqual(status,'rejected-local-action')
        self.assertIn('Not enough',result['exception']['message'])
        self.assertEqual(self.state.data['game_state']['all_villagers']['1']['job']['job_id'],1)

    def test_wrong_baby_and_partial_requests_do_not_apply_mod(self):
        for fields in (dict(villager_id=2,baby_id=900,expected_cost=0),dict(villager_id=2,baby_id=1,expected_cost=0,partial='true')):
            _,status=self.request('game/points/speed_up_parenting',**fields)
            self.assertEqual(status,'rejected-local-action')
        self.assertEqual(self.state.data.get('local_mod_history',[]),[])

    def test_native_building_callback_finishes_selected_builder_only(self):
        gs=self.state.data['game_state']
        gs['buildings']['90']=g.building(90,8,0,3845,self.now)
        gs['all_villagers']['2']['job']=g.idle_job(self.now)
        gs['all_villagers']['2']['job'].update(job_id=5,source_id=90,build_rate=1)
        result,status=self.request('game/points/finish_building',building_id=90,expected_cost=0)
        self.assertEqual(status,'local-mod-skip-timer')
        self.assertEqual(result['buildings']['90']['state'],1)
        self.assertEqual(result['all_villagers']['2']['job']['job_id'],0)
        self.assertEqual(result['all_villagers']['1']['job']['job_id'],1)
        _,status=self.request('game/points/finish_building',building_id=90,expected_cost=0)
        self.assertEqual(status,'rejected-local-action')
