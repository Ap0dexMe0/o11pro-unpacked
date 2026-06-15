from urllib3.util import connection, parse_url
from dns import message, rdatatype, resolver
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
from requests_toolbelt.adapters.socket_options import SocketOptionsAdapter
from io import BytesIO
from http.cookies import SimpleCookie
from curl_cffi import requests as cffi_requests, CurlOpt, CurlSslVersion, CurlHttpVersion
import ipaddress
import gzip
import requests
import urllib
import http
import ssl
import socket
import socks
import json
import base64
import os
import sys
import cloudscraper

def parse_params(params, name, default=""):
    ret = default
    for p in params:
        if p.split("=")[0] == name and len(p.split("=")) >= 2:
            ret = p[len(p.split("=")[0])+1:]
    return ret

def get_local_config():
    return json.load(open(os.path.abspath(os.path.dirname(sys.modules['__main__'].__file__)) + '/../providers/' + os.path.splitext(os.path.basename(sys.modules['__main__'].__file__))[0] + '.cfg'))

class dns:
    def __init__(self, url):
        self.url = url
        self._orig_create_connection = connection.create_connection
        connection.create_connection = self.patched_create_connection
    def resolve_dns(self, host):
        if len(self.url.split("/"))>=3 and self.url.split("/")[2] == host:
            my_resolver  = resolver.Resolver()
            my_resolver.nameservers = ['1.1.1.1']
            return str(my_resolver.query(host)[0])

        try:
            ipaddress.ip_address(host)
            return host
        except:
            pass

        if self.url.startswith('http'):
            headers = {
                    'accept': 'application/dns-message',
                    'content-type': 'application/dns-message',
                    }

            q = message.make_query(host, rdatatype.A)
            response = requests.post(self.url, data=q.to_wire(), headers=headers)
            try:
                return message.from_wire(response.content).answer[0].to_rdataset()[0].to_text()
            except:
                return host
        else:
            if ':' in self.url:
                url = self.url.split(':')[0]
                port = self.url.split(':')[1]
            else:
                url = self.url
                port = 53

            my_resolver = resolver.Resolver()
            my_resolver.nameservers = [url]
            my_resolver.port = int(port)
            result = resolver.query(host)
            return str(my_resolver.query(host)[0])

    def patched_create_connection(self, address, *args, **kwargs):
        host, port = address
        hostname = self.resolve_dns(host)
        return self._orig_create_connection((hostname, port), *args, **kwargs)

class Custom_Adapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.worker = kwargs.pop('worker', None)
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, ssl_version=None, source_address=(), socket_options=[]):
        if ssl_version:
            ssl_context = ssl.create_default_context()
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.options = ssl.PROTOCOL_TLS & ssl.OP_NO_TLSv1_3
            self.poolmanager = PoolManager(num_pools=connections,
                    maxsize=maxsize,
                    block=block,
                    source_address=source_address,
                    socket_options=socket_options,
                    ssl_context=ssl_context)
        else:
            self.poolmanager = PoolManager(num_pools=connections,
                    maxsize=maxsize,
                    block=block,
                    source_address=source_address,
                    socket_options=socket_options)

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        parsed = parse_url(request.url)
        if self.worker and parsed.scheme in ('http', 'https'):
            request.headers['original-host'] = parsed.host
            if parsed.query:
                new_url = f"{parsed.scheme}://{self.worker}{parsed.path}?{parsed.query}"
            else:
                new_url = f"{parsed.scheme}://{self.worker}{parsed.path}"
            request.url = new_url
        return super().send(request, stream, timeout, verify, cert, proxies)

class session1:
    def __init__(self, bind="", proxy="", worker="", force_tls1_2=False, cloud=False):
        if cloud:
            self.session = cloudscraper.create_scraper()
        else:
            self.session = requests.Session()

        if proxy != "":
            self.session.proxies = { "http": proxy, "https": proxy }

        if cloud:
            return

        self.session.mount('http://', Custom_Adapter(worker=worker))
        self.session.mount('https://', Custom_Adapter(worker=worker))

        if bind != "":
            if "." not in bind:
                socket_options = [(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, bind.encode())]
                source_address = ("", 0)
            else:
                socket_options = []
                source_address = (bind, 0)
        else:
            source_address = ("", 0)
            socket_options = []
        if force_tls1_2:
            ssl_version = ssl.PROTOCOL_TLSv1_2
        else:
            ssl_version = None

        self.session.get_adapter('http://').init_poolmanager(
                connections=requests.adapters.DEFAULT_POOLSIZE,
                maxsize=requests.adapters.DEFAULT_POOLSIZE,
                source_address=source_address,
                socket_options=socket_options
                )
        self.session.get_adapter('https://').init_poolmanager(
                connections=requests.adapters.DEFAULT_POOLSIZE,
                maxsize=requests.adapters.DEFAULT_POOLSIZE,
                source_address=source_address,
                socket_options=socket_options,
                ssl_version=ssl_version
                )

    def get_session(self):
        return self.session

class Cookies:
    def __init__(self, cookie_string):
        self.cookies = self._parse_cookies(cookie_string)

    def _parse_cookies(self, cookie_header):
        cookies = {}
        if cookie_header:
            simple_cookie = SimpleCookie(cookie_header)
            for key, morsel in simple_cookie.items():
                cookies[key] = morsel.value
        return cookies

    def get_dict(self):
        return self.cookies

    def clear(self):
        self.cookies.clear()

    def update(self, new_cookies):
        if isinstance(new_cookies, str):
            # Parse the cookie string and update existing cookies
            new_cookie_dict = self._parse_cookies(new_cookies)
            self.cookies.update(new_cookie_dict)
        elif isinstance(new_cookies, dict):
            # If it's already a dictionary, just update the existing cookies
            self.cookies.update(new_cookies)
        else:
            raise ValueError("new_cookies must be either a string or a dictionary.")

class HttpResponse:
    def __init__(self, response):
        self.status = response.status
        self.headers = dict(response.getheaders())
        self._body = response.read()
        for key, value in self.headers.items():
            if key.lower() == 'content-encoding' and value.lower() == 'gzip':
                compressed_data = self._body
                with gzip.GzipFile(fileobj=BytesIO(compressed_data), mode='rb') as f:
                    self._body = f.read()
        
        self.cookies = Cookies(self.headers.get('Set-Cookie', ''))

    @property
    def content(self):
        """Returns the raw response content (bytes)."""
        return self._body

    @property
    def text(self):
        """Returns the response content as a string (decoded)."""
        try:
            return self._body.decode("utf-8")
        except:
            return self._body

    @property
    def status_code(self):
        """Returns the response status code."""
        return self.status

    def json(self):
        """Returns the response content as a parsed JSON object."""
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            raise ValueError("Response content is not valid JSON")

def resolve_dns(hostname, dns_server, ipv6):
    r = resolver.Resolver()
    r.nameservers = [dns_server]

    reso = 'A'
    if ipv6:
        reso = 'AAAA'
    answer = r.query(hostname, reso)
    ip_address = answer[0].address

    return ip_address

class session_http_client:
    def __init__(self, bind="", proxy="", doh="", dns="", worker="", force_tls1_2=False, force_tls1_3=False, ciphers=None, max_redirects=5, ipv6=False):
        self.bind = bind
        self.proxy = proxy
        self.proxy_username = None
        self.proxy_password = None
        self.doh = doh
        self.dns = dns
        self.worker = worker
        self.force_tls1_2 = force_tls1_2
        self.force_tls1_3 = force_tls1_3
        self.max_redirects = max_redirects  # Maximum number of redirects
        self.cookies = {}
        self.ciphers = ciphers
        self.ipv6 = ipv6

        if self.proxy:
            proxy_parsed = urllib.parse.urlparse(proxy)
            if proxy_parsed.username and proxy_parsed.password:
                self.proxy_username = proxy_parsed.username
                self.proxy_password = proxy_parsed.password
            self.proxy_host = proxy_parsed.hostname
            self.proxy_port = proxy_parsed.port or 80

    def get_session(self):
        return self

    def _create_connection(self, host, port, ssl_context, ipv6):
        if ipv6:
            print("Using IPV6", file=sys.stderr)
            af = socket.AF_INET6
        else:
            af = socket.AF_INET

        # Create a socket object
        if self.proxy.startswith('socks'):
            sock = socks.socksocket(af, socket.SOCK_STREAM)
            sock.set_proxy(socks.SOCKS5, self.proxy_host, self.proxy_port, username=self.proxy_username, password=self.proxy_password)
        else:
            sock = socket.socket(af, socket.SOCK_STREAM)
            if ssl_context:
                sock = ssl_context.wrap_socket(sock, server_hostname=host)

        # If bind address is specified, create a socket with the bind address
        if self.bind:
            if "." in self.bind:  # IP address bind
                sock.bind((self.bind, 0))  # Bind to the specified IP address (port 0 to let OS choose)
            else:  # Interface bind (e.g., "eth0")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self.bind.encode())

        # Connect to the host
        if self.doh and self.doh.startswith('http'):
            headers = {
                    'accept': 'application/dns-message',
                    'content-type': 'application/dns-message',
                    }

            q = message.make_query(host, rdatatype.A)
            response = requests.post(self.doh, data=q.to_wire(), headers=headers)
            try:
                host = message.from_wire(response.content).answer[0].to_rdataset()[0].to_text()
                print("DOH: resolved ip to", host, file=sys.stderr)
            except:
                print("DOH failed")
                sys.exit(1)
        elif self.dns:
            host = resolve_dns(host, self.dns, self.ipv6)
            print("DNS: resolved ip to", host, file=sys.stderr)

        sock.connect((host, port))
        
        if ssl_context and self.proxy.startswith('socks'):
            sock = ssl_context.wrap_socket(sock, server_hostname=host)

        return sock

    def request(self, method, url, params=None, body=None, headers={}, allow_redirects=True, verify=True, cookies=None):
        if cookies:
            self.cookies.update(cookies)

        if params:
            if '?' in url:
                url += "&" + urllib.parse.urlencode(params)
            else:
                url += "?" + urllib.parse.urlencode(params)
        parsed_url = urllib.parse.urlparse(url)

        # Create a connection to the host or proxy if specified
        context = None
        if parsed_url.scheme == "https":
            context = ssl.create_default_context()
            if not verify:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            if self.force_tls1_2:
                context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_3
            if self.force_tls1_3:
                context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
            if self.ciphers:
                #print("setting ciphers: " + self.ciphers, file=sys.stderr)
                context.set_ciphers(self.ciphers)

        connection = None
        redirects = 0
        current_url = url

        if isinstance(body, dict):
            converted = False
            for key, value in headers.items():
                if key.lower() == 'content-type':
                    if 'x-www-form-urlencoded' in value:
                        body = urllib.parse.urlencode(body, quote_via=urllib.parse.quote)
                        converted = True
                    elif 'application/json' in value:
                        body = json.dumps(body)
                        converted = True
            if not converted:
                headers['content-type'] = 'application/x-www-form-urlencoded'
                body = urllib.parse.urlencode(body, quote_via=urllib.parse.quote)

        while redirects <= self.max_redirects:
            host = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
            path = parsed_url.path
            if parsed_url.query:
                path += '?' + parsed_url.query

            if self.worker and parsed_url.scheme in ('http', 'https'):
                headers['original-host'] = parsed.host
                host = self.worker

            if self.proxy and self.proxy.startswith('http'):
               real_host = host
               host = self.proxy_host
               port = self.proxy_port

            if parsed_url.scheme == "https":
                connection = http.client.HTTPSConnection(host, port, context=context)
            else:
                connection = http.client.HTTPConnection(host, port)

            if self.proxy and self.proxy.startswith('http'):
               if self.proxy_username and self.proxy_password:
                   auth = base64.b64encode(f"{self.proxy_username}:{self.proxy_password}".encode()).decode()
                   connection.set_tunnel(real_host, headers={'Proxy-Authorization': 'Basic ' + auth})
               else:
                   connection.set_tunnel(real_host)

            if not self.proxy or self.proxy.startswith('socks'):
                connection.sock = self._create_connection(host, port, context, self.ipv6)

            if self.cookies and self.cookies != {}:
                headers['cookie'] = "; ".join([f"{key}={value}" for key, value in self.cookies.items()])

            connection.request(method, path, body=body, headers=headers)
            #if connection.sock:
            #    print("selected ciphers: ", connection.sock.cipher(), file=sys.stderr)
            response = connection.getresponse()
            response = HttpResponse(response)

            self.cookies.update(response.cookies.get_dict())

            if not allow_redirects:
                break

            # Check for redirects (HTTP 3xx status codes)
            if response.status_code in (301, 302, 303, 307, 308):
                if 'location' in response.headers or 'Location' in response.headers:
                    if 'location' in response.headers:
                        location = response.headers['location']
                    else:
                        location = response.headers['Location']
                    current_url = urllib.parse.urljoin(current_url, location)
                    parsed_url = urllib.parse.urlparse(current_url)  # Reparse the new URL
                    redirects += 1
                    print(f"redirect to {location}", file=sys.stderr)
                    continue  # If a redirect, follow it

            # If no redirect, break the loop and return the response
            break

        return response

    def get(self, url, headers={}, params=None, allow_redirects=True, verify=True, cookies=None):
        headers = { k.lower(): v for k, v in headers.items() }
        return self.request("GET", url, params=params, headers=headers, allow_redirects=allow_redirects, verify=verify, cookies=cookies)

    def post(self, url, params=None, data=None, json=None, headers={}, allow_redirects=True, verify=True, cookies=None):
        headers = { k.lower(): v for k, v in headers.items() }
        if json:
            data = json
            headers['content-type'] = 'application/json;charset=UTF-8'
        return self.request("POST", url, params=params, body=data, headers=headers, allow_redirects=allow_redirects, verify=verify, cookies=cookies)

    def put(self, url, params=None, data=None, json=None, headers={}, allow_redirects=True, verify=True, cookies=None):
        headers = { k.lower(): v for k, v in headers.items() }
        if json:
            data = json
            headers['content-type'] = 'application/json;charset=UTF-8'
        return self.request("PUT", url, params=params, body=data, headers=headers, allow_redirects=allow_redirects, verify=verify, cookies=cookies)

    def delete(self, url, params=None, headers={}, allow_redirects=True, verify=True, cookies=None):
        headers = { k.lower(): v for k, v in headers.items() }
        return self.request("DELETE", url, params=params, headers=headers, allow_redirects=allow_redirects, verify=verify, cookies=cookies)

class session_curl_cffi:
    def __init__(self, bind="", proxy="", worker="", doh="", dns="", impersonate="", force_tls1_2=False, force_tls1_3=False, ciphers=None, ipv6=False, verbose=False):
        if doh != "":
            print("DOH not supported with curl_cffi")
            sys.exit(1)
        if dns != "":
            print("DNS not supported with curl_cffi")
            sys.exit(1)
        if worker != "":
            print("Worker not supported with curl_cffi")
            sys.exit(1)

        if force_tls1_2:
            curl_options = { CurlOpt.SSLVERSION: CurlSslVersion.TLSv1_2 }
        elif force_tls1_3:
            curl_options = { CurlOpt.SSLVERSION: CurlSslVersion.TLSv1_3 }
        else:
            curl_options = {}

        if verbose:
            curl_options[CurlOpt.VERBOSE] = True

        self._session = cffi_requests.Session(interface=bind, impersonate=impersonate, curl_options=curl_options)

        if proxy != "":
            self._session.proxies = {
                "http":  proxy,
                "https": proxy
                }

    def get_session(self):
        return self._session

mydns = dns
class session:
    def __init__(self, bind="", proxy="", doh="", dns="", worker="", impersonate="chrome", force_tls1_2=False, force_tls1_3=False, ciphers=None, ipv6=False, alt=False, curl_cffi=False, cloud=False, verbose=False):
        if curl_cffi:
            print("Using curl_cffi", file=sys.stderr)
            s = session_curl_cffi(bind=bind, proxy=proxy, doh=doh, dns=dns, impersonate=impersonate, worker=worker, force_tls1_2=force_tls1_2, force_tls1_3 = force_tls1_3, ciphers=ciphers, ipv6=ipv6, verbose=verbose)
            self.session = s.get_session()
        elif alt:
            print("Using http.client", file=sys.stderr)
            s = session_http_client(bind=bind, proxy=proxy, doh=doh, dns=dns, worker=worker, force_tls1_2=force_tls1_2, force_tls1_3 = force_tls1_3, ciphers=ciphers, ipv6=ipv6)
            self.session = s.get_session()
        else:
            if cloud:
                print("Using cloudscraper", file=sys.stderr)
                if bind != "" or worker != "":
                    print("cannot use bind and/or worker with cloudscraper")
                    sys.exit(1)
            else:
                print("Using requests", file=sys.stderr)

            if doh != "":
                mydns(doh)
            elif dns != "":
                mydns(dns)

            s = session1(bind=bind, proxy=proxy, worker=worker, force_tls1_2=force_tls1_2, cloud=cloud)
            self.session = s.get_session()

    def get_session(self):
        return self.session

class api:
    def __init__(self, url="", user="", password=""):
        self.url = url
        self.token = ""

        if user != "" and password != "":
            json_data = {
                    'Username': user,
                    'Password': password
                    }
            response = requests.post(url + '/api/login', json=json_data, verify=False)
            try:
                self.token = response.json()['Token']
            except:
                print("O11 API login failed")
                sys.exit(1)

        info = self.get_info()
        if "API error" in info:
            print("Could not connect to O11 API: " + info)
            sys.exit(1)

    def get_info(self):
        headers = {
                'Authorization': self.token
                }

        json_data = {
                    'Id': 'local',
                    }

        response = requests.post(self.url + '/api/server/getinfo', headers=headers, json=json_data, verify=False)
        if response.status_code != 200:
            return f"API error {response.status_code}"
        else:
            return response.text

    def add_stream(self, type="event", provider_id="", name="", id="", autostart=True, start=0, end=0):
        headers = {
                'Authorization': self.token
                }

        json_data = {
                'ProviderId': provider_id,
                'StreamName': name,
                'Stream': {
                    'Type': type,
                    'Name': name,
                    'Id': id,
                    'Autostart': autostart,
                    'Start': start,
                    'End': end
                    },
                }

        response = requests.post(self.url + '/api/stream/add', headers=headers, json=json_data, verify=False)
        print(response.text, file=sys.stderr)

    def edit_stream(self, provider_id="", stream_id="", manifest="", keys=[], start=0, end=0):
        headers = {
                'Authorization': self.token
                }

        json_data = {
                'ProviderId': provider_id,
                'StreamId': stream_id,
                'Manifest': manifest,
                'Keys': keys,
                'Start': start,
                'End': end

                }
        response = requests.post(self.url + '/api/stream/edit', headers=headers, json=json_data, verify=False)
        print(response.text, file=sys.stderr)

    def delete_stream(self, provider_id="", stream_id=""):
        headers = {
                'Authorization': self.token
                }

        json_data = {
                'ProviderId': provider_id,
                'StreamId': stream_id,

                }
        response = requests.post(self.url + '/api/stream/delete', headers=headers, json=json_data, verify=False)
        print(response.text, file=sys.stderr)

    def start_stop_stream(self, action="", provider_id="", stream_id=""):
        headers = {
                'Authorization': self.token
                }

        json_data = {
                'ProviderId': provider_id,
                'StreamId': stream_id
                }

        response = requests.post(self.url + '/api/stream/' + action, headers=headers, json=json_data, verify=False)
        print(response.text, file=sys.stderr)

    def add_job(self, name, cron, description="", script_name="", script_params="" , script_timeout=30):
        headers = {
                'Authorization': self.token
                }
        json_data = {
                'Job': {
                    'Enabled': True,
                    'Name': name,
                    'Description': description,
                    'ScriptName': script_name,
                    'ScriptParams': script_params,
                    'ScriptTimeout': script_timeout,
                    'Cron': cron,
                    }
                }

        response = requests.post(self.url + '/api/job/add', headers=headers, json=json_data, verify=False)
        print(response.text, file=sys.stderr)