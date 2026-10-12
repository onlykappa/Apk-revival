"""Tap Quest's documented fixture protocol. No generic response fabrication."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, pathlib, threading, uuid
from .util import RevivalError, atomic_json, read_json

class Progress:
    def __init__(self,path):
        self.path=pathlib.Path(path); self.lock=threading.RLock()
        self.value=read_json(path) if self.path.exists() else {'coins':0,'level':1}
        if set(self.value)!={'coins','level'} or type(self.value['coins']) is not int or self.value['coins']<0 or self.value['level']!=1+self.value['coins']//10:raise RevivalError('Invalid Tap Quest save; restore a valid backup')
    def get(self):
        with self.lock:return dict(self.value)
    def collect(self):
        with self.lock:
            self.value['coins']+=1;self.value['level']=1+self.value['coins']//10
            atomic_json(self.path,self.value);return dict(self.value)

class Backend:
    def __init__(self,save_path,port=18765):
        self.progress=Progress(save_path);self.token=uuid.uuid4().hex;self.port=port;self.server=None;self.thread=None
    def start(self):
        if self.server:return self
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def respond(self,status,data):
                b=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            def do_GET(self):
                if self.path=='/health':self.respond(200,{'service':'tapquest-v1','token':owner.token})
                elif self.path=='/state':self.respond(200,owner.progress.get())
                else:self.respond(404,{'error':'Unknown documented endpoint'})
            def do_POST(self):
                # No arbitrary player IDs, paths or claimed purchase/authentication behavior.
                if self.path!='/action':self.respond(404,{'error':'Unknown documented endpoint'});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if size<1 or size>1024:raise ValueError('Invalid length')
                    data=json.loads(self.rfile.read(size))
                    if data!={'action':'collect'}:raise ValueError('Unsupported action')
                except (ValueError,TypeError):self.respond(400,{'error':'Expected {"action":"collect"}'});return
                self.respond(200,owner.progress.collect())
        try:self.server=ThreadingHTTPServer(('127.0.0.1',self.port),Handler)
        except OSError as e:raise RevivalError(f'Backend startup failed: port {self.port} unavailable. Stop the conflicting service or change the runtime port and prepare again.') from e
        self.port=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();return self
    def stop(self):
        if self.server:self.server.shutdown();self.server.server_close();self.thread.join(timeout=3);self.server=None
    def __enter__(self):return self.start()
    def __exit__(self,*_):self.stop()
