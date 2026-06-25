#!/usr/bin/env python3
import http.server
import http.cookiejar
import urllib.request
import urllib.error
import urllib.parse
import json
import re
import base64
import time
import sys
import os
import argparse                          # FIX: was missing
import threading
import traceback
import gc
from collections import OrderedDict
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor

CONFIG_FILE = '/tmp/o11pro_orig_urls.json'
PROXY_PORT = 9999
PROXY_BIND = '127.0.0.1'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

MAX_COOKIES_PER_JAR = 50
MAX_CACHED_OPENERS = 20
MANIFEST_CACHE_SIZE = 100
MAX_THREAD_POOL = 32
GC_INTERVAL_SEC = 60
SEGMENT_STREAM_BUF = 65536

# Cached channel URLs (loaded once)
_channel_urls = {}
_channel_urls_lock = threading.Lock()

def _load_channel_urls():
    global _channel_urls
    with _channel_urls_lock:
        if not _channel_urls:
            with open(CONFIG_FILE) as f:
                _channel_urls = json.load(f)
            log(f"Loaded {len(_channel_urls)} channel URLs")
    return _channel_urls

# Bounded CookieJar
class BoundedCookieJar(http.cookiejar.CookieJar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_cookie(self, cookie):
        super().set_cookie(cookie)
        if len(self) > MAX_COOKIES_PER_JAR:
            to_remove = len(self) - MAX_COOKIES_PER_JAR
            cookies = list(self)
            for c in cookies[:to_remove]:
                self.clear(c.domain, c.path, c.name)

# Session/Cookie management
_sessions = {}
_sessions_lock = threading.Lock()
_session_last_access = {}

def _get_jar(domain):
    with _sessions_lock:
        if domain not in _sessions:
            _sessions[domain] = BoundedCookieJar()
        _session_last_access[domain] = time.time()
        return _sessions[domain]

def _evict_stale_sessions(max_age=3600):
    with _sessions_lock:
        now = time.time()
        stale = [d for d, t in _session_last_access.items() if now - t > max_age]
        for d in stale:
            del _sessions[d]
            del _session_last_access[d]
        if stale:
            log(f"Evicted {len(stale)} stale sessions, {len(_sessions)} remaining")

# Cached openers (LRU)
_opener_cache = OrderedDict()
_opener_cache_lock = threading.Lock()

def _get_opener(cookie_jar=None):
    jar_id = id(cookie_jar) if cookie_jar else 0
    with _opener_cache_lock:
        if jar_id in _opener_cache:
            _opener_cache.move_to_end(jar_id)
            return _opener_cache[jar_id]
    handlers = []
    if cookie_jar:
        handlers.append(urllib.request.HTTPCookieProcessor(cookie_jar))
    opener = urllib.request.build_opener(*handlers)
    with _opener_cache_lock:
        _opener_cache[jar_id] = opener
        _opener_cache.move_to_end(jar_id)
        while len(_opener_cache) > MAX_CACHED_OPENERS:
            _opener_cache.popitem(last=False)
    return opener

# URL fetching
def fetch_url(url, timeout=15, cookie_jar=None, referer=None):
    opener = _get_opener(cookie_jar)
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read(), resp.status, resp.headers.get('Content-Type', 'application/octet-stream')
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp else b''
        ct = e.headers.get('Content-Type', 'application/octet-stream') if e.headers else 'text/html'
        return body, e.code, ct
    except (urllib.error.URLError, OSError) as e:
        return b'', 0, 'text/plain'

# Manifest URL rewriting
_compiled_uri_re = re.compile(r'URI="([^"]+)"')

def rewrite_manifest(body, base_url):
    lines = body.split('\n')
    rewritten = []
    for line in lines:
        stripped = line.strip()
        if 'URI="' in stripped and stripped.startswith('#EXT-X-'):
            rewritten.append(_compiled_uri_re.sub(
                lambda m: f'URI="{_abs(m.group(1), base_url)}"', stripped))
        elif stripped and not stripped.startswith('#'):
            rewritten.append(_abs(stripped, base_url))
        else:
            rewritten.append(line)
    return '\n'.join(rewritten)

def _abs(url, base):
    if url.startswith(f'http://127.0.0.1:{PROXY_PORT}') or url.startswith('data:'):
        return url
    resolved = url if url.startswith('http') else urllib.parse.urljoin(base, url)
    return _to_proxy(resolved, base)

def _to_proxy(full_url, referer):
    encoded = base64.urlsafe_b64encode(full_url.encode()).decode().rstrip('=')
    route = '/m/' if urlparse(full_url).path.lower().endswith('.m3u8') else '/s/'
    proxy_url = f"http://127.0.0.1:{PROXY_PORT}{route}{encoded}"
    if referer:
        ref_enc = base64.urlsafe_b64encode(referer.encode()).decode().rstrip('=')
        proxy_url += f"?r={ref_enc}"
    return proxy_url

def _from_proxy(encoded):
    pad = 4 - len(encoded) % 4
    if pad != 4:
        encoded += '=' * pad
    return base64.urlsafe_b64decode(encoded.encode()).decode()

def _get_referer(query_string):
    if not query_string:
        return None
    qs = parse_qs(query_string)
    if 'r' in qs:
        return _from_proxy(qs['r'][0])
    return None

# Stats
_stats = {
    'requests': 0,
    'manifests': 0,
    'segments': 0,
    'bytes_sent': 0,
    'errors': 0,
}
_stats_lock = threading.Lock()

# Request Handler
class RobustHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        with _stats_lock:
            _stats['requests'] += 1
        parsed = urlparse(self.path)
        path = parsed.path
        query = parsed.query
        try:
            if path.startswith('/channel/'):
                self._handle_channel(path, query)
            elif path.startswith('/m/'):
                self._handle_manifest(path, query)
            elif path.startswith('/s/'):
                self._handle_segment(path, query)
            else:
                self._err(404, 'Not found')
        except Exception as e:
            with _stats_lock:
                _stats['errors'] += 1
            try:
                self._err(500, str(e))
            except:
                pass

    def _handle_channel(self, path, query):
        parts = path.split('/')
        if len(parts) >= 4 and parts[3] == 'master.m3u8':
            name = urllib.parse.unquote(parts[2])
            urls = _load_channel_urls()
            if name in urls:
                url = urls[name]
                q = query
                if q:
                    url += ('&' if '?' in url else '?') + q
                jar = _get_jar(urlparse(url).netloc)
                body, st, ct = fetch_url(url, cookie_jar=jar)
                if st == 200:
                    with _stats_lock:
                        _stats['manifests'] += 1
                    rw = rewrite_manifest(body.decode('utf-8', 'replace'), url)
                    self._ok('application/vnd.apple.mpegurl', rw.encode())
                else:
                    self._err(502, f"Upstream {st}")
            else:
                self._err(404, "Channel not found")
        else:
            self._err(400, "Bad channel path")

    def _handle_manifest(self, path, query):
        target = _from_proxy(path[3:])
        referer = _get_referer(query)
        jar = _get_jar(urlparse(target).netloc)
        body, st, ct = fetch_url(target, cookie_jar=jar, referer=referer)
        if st == 200:
            with _stats_lock:
                _stats['manifests'] += 1
            rw = rewrite_manifest(body.decode('utf-8', 'replace'), target)
            self._ok('application/vnd.apple.mpegurl', rw.encode())
        else:
            self._err(502, f"Upstream {st}")

    def _handle_segment(self, path, query):
        target = _from_proxy(path[3:])
        if target.startswith('data:'):
            cp = target.find(',')
            if cp >= 0:
                meta, payload = target[5:cp], target[cp + 1:]
                b = base64.b64decode(payload) if 'base64' in meta else urllib.parse.unquote_to_bytes(payload)
                self._ok('application/octet-stream', b)
                return
        referer = _get_referer(query)
        jar = _get_jar(urlparse(target).netloc)
        headers = {'User-Agent': UA}
        if referer:
            headers['Referer'] = referer
        opener = _get_opener(jar)
        req = urllib.request.Request(target, headers=headers)
        try:
            with opener.open(req, timeout=30) as resp:
                ct = resp.headers.get('Content-Type', 'application/octet-stream')
                content_length = resp.headers.get('Content-Length')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                if content_length:
                    self.send_header('Content-Length', content_length)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                total_sent = 0
                while True:
                    chunk = resp.read(SEGMENT_STREAM_BUF)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        total_sent += len(chunk)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
                with _stats_lock:
                    _stats['segments'] += 1
                    _stats['bytes_sent'] += total_sent
        except urllib.error.HTTPError as e:
            self._err(502, f'Upstream {e.code}')
        except (urllib.error.URLError, OSError) as e:
            self._err(502, f'Fetch error: {type(e).__name__}')
        except Exception as e:
            try:
                self._err(502, str(e))
            except:
                pass

    def _ok(self, ct, body):
        try:
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            with _stats_lock:
                _stats['bytes_sent'] += len(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _err(self, code, msg):
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'text/plain')
            body = msg.encode()
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, *a):
        pass

    def handle(self):
        try:
            BaseHTTPRequestHandler.handle(self)
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            pass
        except Exception:
            pass

# Server with bounded thread pool
class BoundedThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._thread_pool = ThreadPoolExecutor(max_workers=MAX_THREAD_POOL)

    def process_request(self, request, client_address):
        self._thread_pool.submit(self._process_request_thread, request, client_address)

    def _process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

    def handle_error(self, request, client_address):
        pass

# Periodic maintenance
def _maintenance_loop():
    while True:
        time.sleep(GC_INTERVAL_SEC)
        collected = gc.collect()
        _evict_stale_sessions()
        pid = os.getpid()
        rss = _get_rss_kb(pid)
        with _stats_lock:
            s = dict(_stats)
        log(f"STATS: rss={rss}KB reqs={s['requests']} manifests={s['manifests']} "
            f"segments={s['segments']} bytes={s['bytes_sent']//1024//1024}MB "
            f"errors={s['errors']} sessions={len(_sessions)} openers={len(_opener_cache)} "
            f"gc_collected={collected}")

def _get_rss_kb(pid):
    try:
        with open(f'/proc/{pid}/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1])
    except:
        return 0

def log(msg):
    sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# Main
if __name__ == '__main__':
    # FIX: was hardcoded, now accepts CLI arguments
    parser = argparse.ArgumentParser(description='HLS Proxy for o11pro (memory-leak fixed)')
    parser.add_argument('--config', default=CONFIG_FILE,
                        help=f'Path to channel URLs JSON (default: {CONFIG_FILE})')
    parser.add_argument('--port', type=int, default=PROXY_PORT,
                        help=f'Proxy listen port (default: {PROXY_PORT})')
    parser.add_argument('--bind', default=PROXY_BIND,
                        help=f'Proxy bind address (default: {PROXY_BIND})')
    args = parser.parse_args()

    CONFIG_FILE = args.config
    PROXY_PORT = args.port
    PROXY_BIND = args.bind

    _load_channel_urls()
    assert _compiled_uri_re is not None

    maint = threading.Thread(target=_maintenance_loop, daemon=True)
    maint.start()

    print(f"HLS Proxy on {PROXY_BIND}:{PROXY_PORT} (memory-optimized)", flush=True)
    print(f"  Config:       {CONFIG_FILE}", flush=True)
    print(f"  Channels:     {len(_channel_urls)}", flush=True)
    print(f"  Thread pool:  {MAX_THREAD_POOL} workers", flush=True)
    print(f"  Cookie limit: {MAX_COOKIES_PER_JAR}/jar", flush=True)
    print(f"  Streaming buffer: {SEGMENT_STREAM_BUF} bytes", flush=True)
    print(f"  GC interval:  {GC_INTERVAL_SEC}s", flush=True)
    print(f"", flush=True)
    print(f"  Routes:", flush=True)
    print(f"    /channel/{{name}}/master.m3u8  - Channel master manifest", flush=True)
    print(f"    /m/{{b64_url}}                 - Manifest fetch+rewrite", flush=True)
    print(f"    /s/{{b64_url}}                 - Segment stream", flush=True)

    server = BoundedThreadedServer((PROXY_BIND, PROXY_PORT), RobustHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()