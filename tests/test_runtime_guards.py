import unittest
from apk_revival.runtime import OfflineGuard,WaydroidRuntime
from apk_revival.util import RevivalError

class Guest:
    def __init__(self,fail_ipv6=False,external_success=False):self.commands=[];self.fail_ipv6=fail_ipv6;self.external_success=external_success
    def shell(self,*args,**kwargs):
        self.commands.append(args)
        if args==('su','0','id','-u'):return '0\n'
        if self.fail_ipv6 and args[:4]==('su','0','ip6tables','-N'):raise RevivalError('Guest ip6tables unavailable')
        return 'recorded rules\n'
    def adb(self,*args,**kwargs):
        if self.external_success:return ''
        raise RevivalError('Connection rejected')

class RuntimeGuardTests(unittest.TestCase):
    def test_guard_attaches_and_cleans_both_families(self):
        g=Guest()
        with OfflineGuard(g) as guard:
            self.assertIn('iptables',guard.evidence);self.assertIn('ip6tables',guard.evidence);chain=guard.chain
        for family in ['iptables','ip6tables']:
            self.assertIn(('su','0',family,'-I','OUTPUT','1','-j',chain),g.commands);self.assertIn(('su','0',family,'-D','OUTPUT','-j',chain),g.commands);self.assertIn(('su','0',family,'-X',chain),g.commands)
    def test_ipv6_failure_never_downgrades_and_cleans_ipv4(self):
        g=Guest(fail_ipv6=True);guard=OfflineGuard(g)
        with self.assertRaisesRegex(RevivalError,'ip6tables'):guard.__enter__()
        self.assertIn(('su','0','iptables','-D','OUTPUT','-j',guard.chain),g.commands);self.assertIn(('su','0','iptables','-X',guard.chain),g.commands)
    def test_successful_external_probe_refuses_certification(self):
        g=Guest(external_success=True);guard=OfflineGuard(g)
        with self.assertRaisesRegex(RevivalError,'negative probe succeeded'):guard.__enter__()
        self.assertIn(('su','0','ip6tables','-X',guard.chain),g.commands)
    def test_guest_health_must_match_this_backend_nonce(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        r=WaydroidRuntime('explicit-guest');r.backend=SimpleNamespace(port=12345,token='fresh-unique-nonce')
        with patch.object(r,'adb',return_value='HTTP/1.0 200 OK\n{"token":"wrong-instance"}'):
            with self.assertRaisesRegex(RevivalError,'probe failed'):r.probe_backend()
        with patch.object(r,'adb',return_value='HTTP/1.0 200 OK\n{"token":"fresh-unique-nonce"}'):self.assertIn('fresh-unique-nonce',r.probe_backend())


class GuestHTTPProbeTests(unittest.TestCase):
    def test_request_is_generated_inside_guest_not_adb_stdin(self):
        import shlex
        from types import SimpleNamespace
        from unittest.mock import patch
        runtime=WaydroidRuntime('explicit-guest');runtime.backend=SimpleNamespace(port=12345,token='fresh-unique-nonce')
        with patch.object(runtime,'adb',return_value='HTTP/1.0 200 OK\n{\"token\":\"fresh-unique-nonce\"}') as adb:
            runtime.probe_backend()
        self.assertEqual(adb.call_args.args[:2],('shell','-T'));self.assertNotIn('input',adb.call_args.kwargs)
        script=adb.call_args.args[2];self.assertIn('toybox sleep 1',script);self.assertIn('-q 2',script)
        parts=shlex.split(script);self.assertTrue(any('GET /health HTTP/1.0\r\n' in part for part in parts))
    def test_empty_response_identifies_failed_http_stage(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        runtime=WaydroidRuntime('explicit-guest');runtime.backend=SimpleNamespace(port=12345,token='fresh-unique-nonce')
        with patch.object(runtime,'adb',return_value=''):
            with self.assertRaisesRegex(RevivalError,'no HTTP response'):runtime.probe_backend()
