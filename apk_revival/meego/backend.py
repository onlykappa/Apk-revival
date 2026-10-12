"""Owned loopback responder with fresh guest-verifiable health identity."""
import json,pathlib,threading,uuid
from urllib.parse import urlsplit
from ..util import RevivalError,read_json,digest
from .engine import server,local_game
_lock=threading.Lock()

class MeegoBackend:
    def __init__(self,data,config,port):self.data=pathlib.Path(data);self.config=pathlib.Path(config);self.port=port;self.token=uuid.uuid4().hex;self.server=None;self.thread=None;self.owned=False
    def start(self):
        if not _lock.acquire(False):raise RevivalError('Another Meego local service is running in this application')
        self.owned=True
        try:
            local_game.RULES=read_json(self.config/'local-rules.json');state=server.State(self.data,read_json(self.config/'starter-packet.json'));token=self.token
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
