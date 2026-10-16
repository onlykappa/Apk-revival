import json,pathlib,tempfile,unittest
from unittest.mock import patch
from apk_revival.launcher.runtime_setup import RuntimeManager

class BridgeDiscoveryTests(unittest.TestCase):
    identity={'link':'actual-bridge','name':'eth0','hwaddr':'00:16:3e:f9:d3:03'}
    def command(self,args,**kwargs):
        if args[-1]=='status':return 'Session: RUNNING\nContainer: RUNNING\nIP address: UNKNOWN\nWayland display: actual-private\n'
        if '--property=ActiveState' in args:return 'active\n'
        if 'devices' in args:return self.devices
        if 'neigh' in args:return json.dumps([{'dst':'192.168.240.99','lladdr':self.identity['hwaddr']}])
        if 'connect' in args:return 'connected to '+args[-1]
        raise AssertionError(args)
    def guest(self,*args,**kwargs):
        if args[0]=='cat':return self.identity['hwaddr']+'\n'
        if args[0]=='ip':return '2: eth0: <UP>\n    inet 192.168.240.99/24 scope global eth0\n'
        raise AssertionError(args)
    def discover(self,**kwargs):
        manager=RuntimeManager()
        with patch.object(manager,'bridge_identity',return_value=self.identity),patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda name:name),patch('apk_revival.launcher.runtime_setup.command',side_effect=self.command),patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=self.guest):
            return manager.discover(**kwargs)
    def test_missing_dhcp_ip_uses_verified_connected_guest(self):
        self.devices='List of devices attached\n192.168.240.99:5555 device product:spoofed\n'
        info=self.discover();self.assertTrue(info['ready']);self.assertEqual(info['ip'],'192.168.240.99');self.assertEqual(info['ip_source'],'verified_container_network_identity');self.assertEqual(info['wayland_display'],'actual-private')
    def test_wrong_mac_never_selects_wifi_phone(self):
        self.devices='List of devices attached\n192.168.240.99:5555 device\n';self.guest=lambda *args,**kwargs:'aa:bb:cc:dd:ee:ff'
        info=self.discover();self.assertFalse(info['ready']);self.assertIsNone(info['ip'])
    def test_same_mac_but_different_current_ip_rejects_stale_transport(self):
        self.devices='List of devices attached\n192.168.240.112:5555 device\n'
        info=self.discover(connect=False);self.assertFalse(info['ready']);self.assertIsNone(info['ip'])
    def test_usb_and_emulator_are_not_identity_candidates(self):
        self.devices='List of devices attached\nusb-phone device\nemulator-5554 device\n'
        with patch.object(self,'guest',side_effect=AssertionError('Must not probe unrelated transports')):
            info=self.discover(connect=False)
        self.assertFalse(info['ready'])
    def test_reconnect_uses_configured_bridge_neighbor_then_verifies_guest(self):
        self.devices='List of devices attached\n'
        manager=RuntimeManager()
        with patch.object(manager,'bridge_identity',return_value=self.identity),patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda name:name),patch('apk_revival.launcher.runtime_setup.command',side_effect=self.command) as run,patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=self.guest):info=manager.discover()
        self.assertTrue(info['ready']);self.assertIn(['ip','-j','neigh','show','dev','actual-bridge'],[call.args[0] for call in run.call_args_list]);self.assertIn(['adb','connect','192.168.240.99:5555'],[call.args[0] for call in run.call_args_list])
    def test_read_only_discovery_does_not_reconnect_or_query_neighbors(self):
        self.devices='List of devices attached\n'
        manager=RuntimeManager()
        with patch.object(manager,'bridge_identity',return_value=self.identity),patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda name:name),patch('apk_revival.launcher.runtime_setup.command',side_effect=self.command) as run:info=manager.discover(connect=False)
        self.assertFalse(info['ready']);self.assertFalse(any('connect' in call.args[0] or 'neigh' in call.args[0] for call in run.call_args_list))
    def test_ambiguous_verified_transports_are_not_selected(self):
        self.devices='List of devices attached\n192.168.240.99:5555 device\n192.168.240.100:5555 device\n'
        self.guest=lambda *args,**kwargs:self.identity['hwaddr'] if args[0]=='cat' else 'inet 192.168.240.99/24\ninet 192.168.240.100/24'
        self.assertFalse(self.discover()['ready'])
    def test_runtime_snapshot_records_missing_dhcp_and_verified_fallback(self):
        self.devices='List of devices attached\n192.168.240.99:5555 device\n'
        with tempfile.TemporaryDirectory() as temp:
            path=pathlib.Path(temp)/'runtime-state.json';manager=RuntimeManager(path)
            with patch.object(manager,'bridge_identity',return_value=self.identity),patch('apk_revival.launcher.runtime_setup.tool',side_effect=lambda name:name),patch('apk_revival.launcher.runtime_setup.command',side_effect=self.command),patch('apk_revival.launcher.runtime_setup.WaydroidRuntime.shell',side_effect=self.guest):manager.discover()
            saved=json.loads(path.read_text());self.assertIn('UNKNOWN',saved['status_output']);self.assertEqual(saved['ip_source'],'verified_container_network_identity')
