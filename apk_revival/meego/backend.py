"""Owned loopback responder with fresh guest-verifiable health identity."""
import json,pathlib,threading,uuid,plistlib,zipfile
from urllib.parse import urlsplit
from ..util import RevivalError,read_json,digest
from .engine import server,local_game,birthstones
_lock=threading.Lock()

class MeegoBackend:
    def __init__(self,data,config,port,*,apk=None):self.data=pathlib.Path(data);self.config=pathlib.Path(config);self.port=port;self.apk=apk;self.token=uuid.uuid4().hex;self.server=None;self.thread=None;self.owned=False
    def start(self):
        if not _lock.acquire(False):raise RevivalError('Another Meego local service is running in this application')
        self.owned=True
        try:
            rules=read_json(self.config/'local-rules.json')
            if self.apk is not None:
                # Read additional original rules for already prepared clients;
                # do not rewrite/hash-break their private service-data files.
                with zipfile.ZipFile(self.apk) as archive:
                    tree=plistlib.loads(archive.read('assets/TechTree.plist'))['techtree']
                for name in ('birthsigns','achievements','client_data','dungeon_types','dungeon_stages'):
                    if name in tree:rules[name]=tree[name]
                rules['birthsigns']=birthstones.load_catalog(self.apk)
            seed=read_json(self.config/'starter-packet.json')
            birthstones.populate_packet(seed,rules.get('birthsigns',{}))
            local_game.RULES=rules;state=server.State(self.data,seed);token=self.token
            class Handler(server.Handler):
                def dispatch(inner):
                    if urlsplit(inner.path).path=='/health':inner.reply(200,{'token':token,'package':server.PACKAGE,'status':'experimental-local-simulation'});return
                    super().dispatch()
                do_GET=dispatch
                do_POST=dispatch
            self.server=server.ThreadingHTTPServer(('127.0.0.1',self.port),Handler);self.server.state=state;self.port=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();return self
        except Exception as e:self.stop();raise RevivalError('Meego backend startup failed: '+str(e)) from e
    def stop(self):
        if self.server:
            if self.thread and self.thread.is_alive():self.server.shutdown();self.thread.join(timeout=5)
            self.server.server_close();self.server=None
        if self.owned:self.owned=False;_lock.release()

def config_path(store,p):
    entry=p['restoration'].get('backend_data');root=store.directory(p['id'])
    if not entry:raise RevivalError('Prepare Meego local service data first')
    path=(root/entry['directory']).resolve()
    if root.resolve() not in path.parents:raise RevivalError('Unsafe backend data location')
    for name,sha in entry['files'].items():
        if pathlib.PurePosixPath(name).name!=name or digest(path/name)!=sha:raise RevivalError('Meego backend data changed. Prepare again.')
    return path

