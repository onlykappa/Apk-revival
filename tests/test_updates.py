import io,json,os,pathlib,ssl,tarfile,tempfile,unittest,urllib.request
from unittest.mock import patch
from apk_revival.launcher.network import tls_context,open_url
from apk_revival.launcher.updater import Updater,API,stage_archive,version
from apk_revival.launcher.install import install
from apk_revival.util import RevivalError

class Reply(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

class UpdateTests(unittest.TestCase):
    def test_portable_roots_with_missing_system_certificates(self):
        with patch.dict(os.environ,{'SSL_CERT_FILE':'/nonexistent/ca.pem','SSL_CERT_DIR':'/nonexistent/ca'}):
            context=tls_context()
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED);self.assertTrue(context.check_hostname);self.assertGreater(len(context.get_ca_certs()),100)
    def test_downloads_use_verified_context(self):
        with patch('apk_revival.launcher.network.urllib.request.urlopen') as call:
            open_url('https://example.com')
        self.assertEqual(call.call_args.kwargs['context'].verify_mode,ssl.CERT_REQUIRED)
    def test_release_selection_includes_existing_prerelease_channel(self):
        def release(v,draft=False):
            return {'tag_name':v,'draft':draft,'prerelease':True,'assets':[{'name':'APK-Revival-'+v[1:]+'-linux-x86_64.tar.gz','url':API+'/releases/assets/1'},{'name':'SHA256SUMS.txt','url':API+'/releases/assets/2'}]}
        updater=Updater()
        with patch.object(updater,'request',return_value=Reply(json.dumps([release('v0.3.0'),release('v0.4.0'),release('v0.5.0',True)]).encode())):result=updater.check()
        self.assertEqual(result['version'],'0.4.0')
    def test_credentials_are_stripped_on_redirect(self):
        updater=Updater('private-test-value');seen={}
        def build(*handlers):
            redirect=handlers[0];req=urllib.request.Request(API+'/releases/assets/1',headers={'Authorization':'Bearer private-test-value'})
            redirected=redirect.redirect_request(req,None,302,'',{},'https://release-assets.githubusercontent.com/item');self.assertFalse(redirected.has_header('Authorization'))
            class Opener:
                def open(self,req,timeout):seen['auth']=req.get_header('Authorization');return Reply(b'{}')
            return Opener()
        with patch('urllib.request.build_opener',side_effect=build):updater.request(API+'/releases',asset=False)
        self.assertEqual(seen['auth'],'Bearer private-test-value')
        with self.assertRaisesRegex(RevivalError,'origin'):updater.request('https://evil.example/file')
    def test_bad_checksum_refuses_download(self):
        updater=Updater();updater.release={'version':'0.4.0','package':{'name':'update.tar.gz','url':API+'/releases/assets/1'},'checksums':{'url':API+'/releases/assets/2'}}
        with tempfile.TemporaryDirectory() as home,patch('pathlib.Path.home',return_value=pathlib.Path(home)),patch.object(updater,'request',side_effect=[Reply(('0'*64+'  update.tar.gz\n').encode()),Reply(b'bad')]):
            with self.assertRaisesRegex(RevivalError,'checksum'):updater.stage()
    def archive(self,root,members):
        archive=root/'update.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,data,link in members:
                item=tarfile.TarInfo(name)
                if link:item.type=tarfile.SYMTYPE;item.linkname=link;tar.addfile(item)
                else:item.size=len(data);tar.addfile(item,io.BytesIO(data))
        return archive
    def test_rejects_traversal_external_link_and_duplicate(self):
        cases=[[('../outside',b'x',None)],[('APK-Revival/x',b'', '../../outside')],[('APK-Revival/x',b'x',None),('APK-Revival/x',b'y',None)]]
        for members in cases:
            with self.subTest(members=members),tempfile.TemporaryDirectory() as home,patch('pathlib.Path.home',return_value=pathlib.Path(home)):
                with self.assertRaises(RevivalError):stage_archive(self.archive(pathlib.Path(home),members))
                self.assertFalse((pathlib.Path(home)/'outside').exists())
    def test_update_probe_strips_private_libcrypto_from_inherited_loader_path(self):
        from apk_revival.launcher.updater import stage_archive
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as home,patch('pathlib.Path.home',return_value=pathlib.Path(home)):
            root=pathlib.Path(home)
            archive=self.archive(root,[('APK-Revival/APK-Revival',b'fake',None),('APK-Revival/_internal/library',b'fake',None)])
            private='/home/deck/.cache/apk-revival/updates/old/APK-Revival/_internal'
            variables={'LD_LIBRARY_PATH':private,'LD_LIBRARY_PATH_ORIG':private}
            with patch.dict(os.environ,variables),patch('apk_revival.util.sys.frozen',True,create=True):
                with patch('subprocess.run',return_value=CompletedProcess([],0,json.dumps({'version':'0.4.0','certificates':True}),'')) as process:
                    stage_archive(archive,expected_version='0.4.0')
            self.assertNotIn('LD_LIBRARY_PATH',process.call_args.kwargs['env'])
            self.assertNotIn('LD_LIBRARY_PATH_ORIG',process.call_args.kwargs['env'])

    def test_staging_checks_version_and_keeps_installed_app(self):
        with tempfile.TemporaryDirectory() as home,patch('pathlib.Path.home',return_value=pathlib.Path(home)):
            root=pathlib.Path(home);installed=root/'.local/share/apk-revival-app';installed.mkdir(parents=True);(installed/'APK-Revival').write_text('old')
            archive=self.archive(root,[('APK-Revival/APK-Revival',b'fake',None),('APK-Revival/_internal/library',b'fake',None)])
            from subprocess import CompletedProcess
            with patch('subprocess.run',return_value=CompletedProcess([],0,json.dumps({'version':'0.4.0','certificates':True}),'')):result=stage_archive(archive,expected_version='0.4.0')
            self.assertTrue(pathlib.Path(result['directory']).is_dir());self.assertEqual((installed/'APK-Revival').read_text(),'old')
            with patch('subprocess.run',return_value=CompletedProcess([],1,'','bad')):
                with self.assertRaisesRegex(RevivalError,'cannot start'):stage_archive(archive)
    def test_missing_install_does_not_touch_current_app(self):
        with tempfile.TemporaryDirectory() as home:
            root=pathlib.Path(home);target=root/'.local/share/apk-revival-app';target.mkdir(parents=True);(target/'APK-Revival').write_text('old');source=root/'bad';source.mkdir()
            with self.assertRaisesRegex(RevivalError,'missing'):install(source,root)
            self.assertEqual((target/'APK-Revival').read_text(),'old')
    def test_failed_swap_restores_previous_app(self):
        with tempfile.TemporaryDirectory() as home:
            root=pathlib.Path(home);source=root/'source';source.mkdir();(source/'APK-Revival').write_text('new');target=root/'.local/share/apk-revival-app';target.mkdir(parents=True);(target/'APK-Revival').write_text('old');real=pathlib.Path.rename
            def rename(path,dest):
                if path.name=='apk-revival-app.new':raise OSError('test swap failure')
                return real(path,dest)
            with patch('pathlib.Path.rename',rename):
                with self.assertRaises(OSError):install(source,root)
            self.assertEqual((target/'APK-Revival').read_text(),'old')

class UpdateUI(unittest.TestCase):
    @unittest.skipUnless(os.getenv('QT_QPA_PLATFORM')=='offscreen','Qt offscreen test')
    def test_setup_update_controls_and_no_update_result(self):
        from PySide6.QtWidgets import QApplication,QPushButton
        from apk_revival.launcher.ui import Window
        from apk_revival.store import Store
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as t:
            window=Window(Store(pathlib.Path(t)));buttons={b.text() for b in window.setup.findChildren(QPushButton)}
            self.assertTrue({'Check for updates','GitHub access','Install downloaded update'}.issubset(buttons))
            window.update_checked({'available':False,'version':'0.3.1'});self.assertIn('up to date',window.update_label.text());window.close();app.processEvents()

    def test_update_check_waits_for_a_running_task_instead_of_being_dropped(self):
        import time
        from PySide6.QtWidgets import QApplication
        from apk_revival.launcher.ui import Window
        from apk_revival.store import Store
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as t:
            window=Window(Store(pathlib.Path(t)));window.updater.check=lambda progress=None:{'available':False,'version':'0.3.8'}
            window.submit('Check Android setup',lambda ctx:time.sleep(.3));window.check_updates()
            self.assertIn('will start when check Android setup finishes',window.message.text())
            end=time.monotonic()+10
            while (window.worker or window.queued) and time.monotonic()<end:app.processEvents();time.sleep(.02)
            self.assertIn('up to date',window.update_label.text());window.close();app.processEvents()

class ApplyUpdateTests(unittest.TestCase):
    def test_restart_after_old_process_exits_preserves_data(self):
        from apk_revival.launcher.updater import apply_update
        with tempfile.TemporaryDirectory() as home:
            root=pathlib.Path(home);source=root/'staged';source.mkdir();(source/'APK-Revival').write_text('new');data=root/'games';data.mkdir();(data/'save.json').write_text('saved')
            with patch('pathlib.Path.home',return_value=root),patch('os.kill',side_effect=ProcessLookupError),patch('subprocess.Popen') as popen:
                self.assertEqual(apply_update(str(source),12345,True,str(data)),0)
            args=popen.call_args.args[0];self.assertIn('--fullscreen',args);self.assertEqual(args[-2:],['--data',str(data)]);self.assertEqual((data/'save.json').read_text(),'saved')
