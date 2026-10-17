"""A local HTTP proxy that logs which servers a game contacts and can stand in for dead ones.

Android's global HTTP proxy points at this server through `adb reverse`, so it only
listens on the host's loopback interface. Modes:
- 'log': relay traffic normally and record each server contacted.
- 'offline': no internet. Plain HTTP gets an immediate empty 200 reply; HTTPS
  (CONNECT) is refused at once, so games fail fast instead of waiting for timeouts.
HTTPS contents are never decrypted; only the server name and port are recorded.
URL query strings are dropped from the log because they often carry tokens.
"""
from __future__ import annotations
import json, pathlib, select, socket, socketserver, threading, time
from urllib.parse import urlsplit

MAX_HEADER = 64 * 1024
MAX_LOG_LINES = 5000
OFFLINE_BODY = b'{}'


class Proxy:
    def __init__(self, log_file, mode='log', port=0):
        if mode not in ('log', 'offline'):
            raise ValueError('Unknown proxy mode')
        self.log_file, self.mode, self.port = pathlib.Path(log_file), mode, port
        self.lock = threading.Lock()
        self.lines = 0
        self.server = None
        self.thread = None

    def record(self, **entry):
        entry['time'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        entry['answered'] = 'offline' if self.mode == 'offline' else 'relayed'
        with self.lock:
            if self.lines >= MAX_LOG_LINES:
                return
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file.open('a') as out:
                out.write(json.dumps(entry) + '\n')
            self.lines += 1

    def start(self):
        proxy = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                proxy.handle(self.request)

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.server = Server(('127.0.0.1', self.port), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    # One client connection
    def handle(self, client):
        client.settimeout(30)
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = client.recv(4096)
            if not chunk:
                return
            head += chunk
            if len(head) > MAX_HEADER:
                client.sendall(b'HTTP/1.1 431 Request Header Fields Too Large\r\nConnection: close\r\n\r\n')
                return
        header, _, body = head.partition(b'\r\n\r\n')
        lines = header.decode('latin-1').split('\r\n')
        try:
            method, target, version = lines[0].split(' ', 2)
        except ValueError:
            client.sendall(b'HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n')
            return
        if method.upper() == 'CONNECT':
            host, _, port = target.rpartition(':')
            self.record(method='CONNECT', host=host.strip('[]').lower(), port=int(port) if port.isdigit() else 443, secure=True)
            if self.mode == 'offline':
                client.sendall(b'HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
                return
            self.tunnel(client, host.strip('[]'), int(port) if port.isdigit() else 443)
            return
        url = urlsplit(target)
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(':')
            headers[name.strip().lower()] = value.strip()
        host = url.hostname or headers.get('host', '').split(':')[0]
        port = url.port or 80
        self.record(method=method.upper(), host=(host or '').lower(), port=port, path=url.path or '/', secure=False)
        if self.mode == 'offline':
            client.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % len(OFFLINE_BODY) + OFFLINE_BODY)
            return
        self.forward(client, method, url, version, lines[1:], body, host, port, headers)

    def tunnel(self, client, host, port):
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            return
        with upstream:
            client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self.pipe(client, upstream)

    def forward(self, client, method, url, version, header_lines, body, host, port, headers):
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            return
        with upstream:
            path = (url.path or '/') + ('?' + url.query if url.query else '')
            kept = [l for l in header_lines if l.split(':', 1)[0].strip().lower() not in ('connection', 'proxy-connection', 'keep-alive')]
            upstream.sendall(f'{method} {path} {version}\r\n'.encode('latin-1') + '\r\n'.join(kept + ['Connection: close']).encode('latin-1') + b'\r\n\r\n' + body)
            remaining = int(headers.get('content-length', '0') or 0) - len(body)
            while remaining > 0:
                chunk = client.recv(min(65536, remaining))
                if not chunk:
                    break
                upstream.sendall(chunk)
                remaining -= len(chunk)
            self.pipe(client, upstream)

    @staticmethod
    def pipe(a, b):
        sockets = [a, b]
        while True:
            ready, _, _ = select.select(sockets, [], [], 60)
            if not ready:
                return
            for s in ready:
                try:
                    data = s.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                (b if s is a else a).sendall(data)


def summary(log_file):
    """Servers contacted, busiest first: [{'host','port','secure','count','first','last','paths'}]."""
    hosts = {}
    path = pathlib.Path(log_file)
    if not path.exists():
        return []
    for line in path.read_text().splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        key = (entry.get('host'), entry.get('port'), bool(entry.get('secure')))
        item = hosts.setdefault(key, {'host': key[0], 'port': key[1], 'secure': key[2], 'count': 0, 'first': entry.get('time'), 'last': entry.get('time'), 'paths': []})
        item['count'] += 1
        item['last'] = entry.get('time')
        if entry.get('path') and entry['path'] not in item['paths'] and len(item['paths']) < 20:
            item['paths'].append(entry['path'])
    return sorted(hosts.values(), key=lambda x: -x['count'])
