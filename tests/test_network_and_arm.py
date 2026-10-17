"""Per-game network modes (proxy log, offline answers, blocking) and ARM support guidance."""
import http.server, json, os, pathlib, socket, tempfile, threading, unittest
from unittest.mock import patch
from apk_revival import arm_support, game_network
from apk_revival.netproxy import Proxy, summary
from apk_revival.util import RevivalError


def request(port, raw, read=True):
    with socket.create_connection(('127.0.0.1', port), timeout=5) as s:
        s.sendall(raw)
        data = b''
        while read:
            chunk = s.recv(65536)
            if not chunk:break
            data += chunk
        return data


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.log = pathlib.Path(self.temp.name) / 'net.jsonl'
    def tearDown(self): self.temp.cleanup()

    def test_offline_answers_plain_http_instantly_and_never_logs_queries(self):
        proxy = Proxy(self.log, 'offline').start()
        try:
            reply = request(proxy.port, b'GET http://dead.example/api/login?token=SECRET HTTP/1.1\r\nHost: dead.example\r\n\r\n')
            secure = request(proxy.port, b'CONNECT auth.dead.example:443 HTTP/1.1\r\nHost: auth.dead.example:443\r\n\r\n')
        finally:proxy.stop()
        self.assertTrue(reply.startswith(b'HTTP/1.1 200 OK'));self.assertTrue(reply.endswith(b'{}'))
        self.assertTrue(secure.startswith(b'HTTP/1.1 502'))
        text = self.log.read_text();self.assertNotIn('SECRET', text)
        rows = summary(self.log)
        self.assertEqual({(r['host'], r['secure']) for r in rows}, {('dead.example', False), ('auth.dead.example', True)})
        self.assertEqual(next(r for r in rows if not r['secure'])['paths'], ['/api/login'])

    def test_log_mode_relays_http_and_tunnels(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'hello from upstream';self.send_response(200);self.send_header('Content-Length', str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self, *a):pass
        upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler);threading.Thread(target=upstream.serve_forever, daemon=True).start()
        echo = socket.socket();echo.bind(('127.0.0.1', 0));echo.listen()
        def serve_echo():
            conn, _ = echo.accept()
            with conn:conn.sendall(conn.recv(100).upper())
        threading.Thread(target=serve_echo, daemon=True).start()
        proxy = Proxy(self.log, 'log').start()
        try:
            port = upstream.server_address[1]
            reply = request(proxy.port, f'GET http://127.0.0.1:{port}/hello HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n'.encode())
            with socket.create_connection(('127.0.0.1', proxy.port), timeout=5) as s:
                s.sendall(f'CONNECT 127.0.0.1:{echo.getsockname()[1]} HTTP/1.1\r\n\r\n'.encode())
                self.assertTrue(s.recv(100).startswith(b'HTTP/1.1 200'))
                s.sendall(b'ping');self.assertEqual(s.recv(100), b'PING')
        finally:proxy.stop();upstream.shutdown();upstream.server_close();echo.close()
        self.assertIn(b'hello from upstream', reply)
        self.assertEqual({e['answered'] for e in map(json.loads, self.log.read_text().splitlines())}, {'relayed'})

    def test_oversized_headers_and_garbage_are_refused(self):
        proxy = Proxy(self.log, 'offline').start()
        try:
            self.assertIn(b'400', request(proxy.port, b'nonsense\r\n\r\n'))
            self.assertIn(b'431', request(proxy.port, b'GET http://x/ HTTP/1.1\r\nX: ' + b'a' * 70000 + b'\r\n\r\n'))
        finally:proxy.stop()


class FakeAndroid:
    def __init__(self, fail_root=False, listing=''):
        self.commands, self.fail_root, self.listing = [], fail_root, listing
    def shell(self, *args, timeout=60):
        self.commands.append(args)
        if args[:4] == ('cmd', 'package', 'list', 'packages'):return 'package:game.example.helper uid:10099\npackage:game.example uid:10057\n'
        if args[:2] == ('su', '0'):
            if self.fail_root and '-N' in args[-1]:raise RevivalError('su: denied')
            if '-S' in args[-1]:return self.listing
        return ''
    def adb(self, *args, timeout=60):self.commands.append(('adb',) + args);return ''


class GameNetworkTests(unittest.TestCase):
    def test_block_allows_loopback_first_and_targets_only_the_game(self):
        android = FakeAndroid()
        self.assertEqual(game_network.package_uid(android, 'game.example'), 10057)
        game_network.block(android, 10057)
        script = android.commands[-1][-1]
        for tool in ('iptables', 'ip6tables'):
            self.assertIn(f'{tool} -I OUTPUT -m owner --uid-owner 10057 -j APKR_GAME_10057', script)
        self.assertLess(script.index('-o lo -j ACCEPT'), script.index('-j REJECT'))

    def test_failed_block_cleans_up_and_explains(self):
        android = FakeAndroid(fail_root=True)
        with self.assertRaisesRegex(RevivalError, 'root access'):game_network.block(android, 10057)
        self.assertIn('-X APKR_GAME_10057', android.commands[-1][-1])

    def test_leftovers_and_proxy_commands(self):
        android = FakeAndroid(listing='-N APKR_GAME_10057\n-A OUTPUT -m owner --uid-owner 10057 -j APKR_GAME_10057\n-N APKR_GAME_10111\n')
        self.assertEqual(game_network.remove_leftovers(android), [10057, 10111])
        game_network.set_proxy(android, 18900);game_network.clear_proxy(android, 18900)
        self.assertIn(('adb', 'reverse', 'tcp:18900', 'tcp:18900'), android.commands)
        self.assertIn(('settings', 'put', 'global', 'http_proxy', '127.0.0.1:18900'), android.commands)
        self.assertIn(('settings', 'put', 'global', 'http_proxy', ':0'), android.commands)
        self.assertIn(('adb', 'reverse', '--remove', 'tcp:18900'), android.commands)


class ServiceNetworkTests(unittest.TestCase):
    def setUp(self):
        from apk_revival.launcher.service import Launcher
        from apk_revival.store import Store
        self.temp = tempfile.TemporaryDirectory();self.launcher = Launcher(Store(pathlib.Path(self.temp.name)))
        self.p = {'id': 'a' * 24, 'restoration': {}, 'analysis': {'metadata': {'package': 'game.example'}}, 'launcher': {'network': 'offline'}}
    def tearDown(self):self.temp.cleanup()
    class Ctx:
        def step(self, *a):pass

    def test_offline_mode_applies_and_fully_undoes(self):
        android = FakeAndroid()
        self.launcher.start_network(self.p, android, self.Ctx())
        proxy = self.launcher.network['proxy'];self.assertTrue(self.launcher.settings['network_applied'])
        self.assertEqual(request(proxy.port, b'GET http://dead.example/ HTTP/1.1\r\n\r\n')[-2:], b'{}')
        self.launcher.stop_network()
        self.assertIsNone(proxy.server);self.assertFalse(self.launcher.settings['network_applied'])
        self.assertTrue(any(c[:2] == ('su', '0') and '-X APKR_GAME_10057' in c[-1] for c in android.commands))
        self.assertIn(('settings', 'put', 'global', 'http_proxy', ':0'), android.commands)

    def test_failure_rolls_back_and_leftovers_are_cleared_next_time(self):
        android = FakeAndroid(fail_root=True)
        with self.assertRaisesRegex(RevivalError, 'root access'):self.launcher.start_network(self.p, android, self.Ctx())
        self.assertIsNone(self.launcher.network)
        self.assertIn(('settings', 'put', 'global', 'http_proxy', ':0'), android.commands)
        self.launcher.settings['network_applied'] = True
        android = FakeAndroid(listing='-N APKR_GAME_10057\n');self.p['launcher']['network'] = 'normal'
        self.launcher.start_network(self.p, android, self.Ctx())
        self.assertTrue(any('-X APKR_GAME_10057' in c[-1] for c in android.commands if c[:2] == ('su', '0')))
        self.assertFalse(self.launcher.settings['network_applied'])

    def test_normal_mode_changes_nothing(self):
        android = FakeAndroid();self.p['launcher']['network'] = 'normal'
        self.launcher.start_network(self.p, android, self.Ctx())
        self.assertEqual(android.commands, []);self.assertIsNone(self.launcher.network)


class ArmSupportTests(unittest.TestCase):
    ARM_ONLY = {'analysis': {'abis': ['armeabi-v7a', 'arm64-v8a']}}

    def test_detection_and_status(self):
        self.assertTrue(arm_support.needs_arm(self.ARM_ONLY))
        self.assertFalse(arm_support.needs_arm({'analysis': {'abis': ['arm64-v8a', 'x86_64']}}))
        self.assertFalse(arm_support.needs_arm({'analysis': {'abis': []}}))
        with_ndk = arm_support.android_status(['x86_64', 'x86', 'arm64-v8a', 'armeabi-v7a', 'armeabi'], 'libndk_translation.so')
        self.assertEqual((with_ndk['arm'], with_ndk['translator']), (True, 'libndk_translation'))
        plain = arm_support.android_status(['x86_64', 'x86'], '0')
        self.assertFalse(plain['arm']);self.assertIsNone(plain['translator'])
        self.assertIn('no ARM support', arm_support.compatible(self.ARM_ONLY, plain))
        self.assertIsNone(arm_support.compatible(self.ARM_ONLY, with_ndk))
        self.assertIsNone(arm_support.compatible(self.ARM_ONLY, None), 'unknown status never blocks')
        legacy = arm_support.android_status(['x86_64', 'armeabi-v7a'], 'libhoudini.so')
        self.assertIsNone(arm_support.compatible({'analysis': {'abis': ['armeabi']}}, legacy))

    def test_guide_matches_the_processor(self):
        with tempfile.NamedTemporaryFile('w', suffix='cpuinfo') as f:
            f.write('vendor_id\t: AuthenticAMD\n');f.flush()
            self.assertEqual(arm_support.cpu_vendor(f.name), 'amd')
        self.assertIn('install libndk', arm_support.guide('amd')['commands'])
        self.assertIn('install libhoudini', arm_support.guide('intel')['commands'])

    def test_runtime_error_opens_the_guide_and_status_is_remembered(self):
        from apk_revival.runtime import WaydroidRuntime
        from apk_revival.launcher.service import Launcher
        from apk_revival.store import Store
        runtime = WaydroidRuntime('guest')
        runtime.probe = lambda: {'available': True, 'abis': ['x86_64', 'x86'], 'sdk': '30', 'native_bridge': '0'}
        p = {'analysis': {'abis': ['arm64-v8a'], 'metadata': {'min_sdk': '21'}, 'input_errors': []}}
        with tempfile.TemporaryDirectory() as temp:
            launcher = Launcher(Store(pathlib.Path(temp)))
            with self.assertRaises(RevivalError) as caught:launcher.check_compatible(runtime, p)
            self.assertTrue(str(caught.exception).startswith(arm_support.ERROR_PREFIX))
            self.assertIn('Architecture mismatch', str(caught.exception))
            self.assertFalse(launcher.settings['android_arm']['arm'])


if __name__ == '__main__':
    unittest.main()
