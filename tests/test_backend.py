import concurrent.futures, json, pathlib, socket, tempfile, unittest, urllib.error, urllib.request
from apk_revival.backend import Backend, Progress
from apk_revival.util import RevivalError

class BackendTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)/'save.json';self.backend=Backend(self.path,0).start();self.base=f'http://127.0.0.1:{self.backend.port}'
    def tearDown(self):self.backend.stop();self.temp.cleanup()
    def request(self,path,body=None):
        req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'});return json.load(urllib.request.urlopen(req,timeout=5))
    def test_protocol_persistence_and_restart(self):
        self.assertEqual(self.request('/state'),{'coins':0,'level':1})
        for _ in range(10):state=self.request('/action',{'action':'collect'})
        self.assertEqual(state,{'coins':10,'level':2});self.backend.stop();self.backend=Backend(self.path,0).start();self.base=f'http://127.0.0.1:{self.backend.port}';self.assertEqual(self.request('/state'),state)
    def test_concurrent_actions_are_not_lost(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda _:self.request('/action',{'action':'collect'}),range(30)))
        self.assertEqual(self.request('/state'),{'coins':30,'level':4})
    def test_unknown_behavior_rejected(self):
        for path,body,expected in [('/login',None,404),('/action',{'action':'purchase'},400),('/action',{'action':'collect','coins':100},400)]:
            with self.assertRaises(urllib.error.HTTPError) as c:self.request(path,body)
            self.assertEqual(c.exception.code,expected)
        self.assertEqual(self.request('/state')['coins'],0)
    def test_local_bind_and_health_nonce(self):
        self.assertEqual(self.backend.server.server_address[0],'127.0.0.1');token=self.request('/health')['token'];self.backend.stop();self.backend=Backend(self.path,0).start();self.assertNotEqual(self.backend.token,token)
    def test_startup_failure_and_recovery(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));s.listen();port=s.getsockname()[1]
            with self.assertRaisesRegex(RevivalError,'startup failed'):Backend(self.path,port).start()
        with Backend(self.path,port) as recovered:self.assertTrue(recovered.server)
    def test_invalid_save_rejected(self):
        self.backend.stop();self.path.write_text('{"coins":-2,"level":1}')
        with self.assertRaises(RevivalError):Progress(self.path)

if __name__=='__main__':unittest.main()
