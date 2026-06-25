#!/usr/bin/env python3
import os
import sys
import re
import time
import json
import socket
import struct
import signal
import argparse
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict, deque
import http.client
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

VERSION = "1.0.0"
DEFAULT_PID_FILE = "/tmp/o11_pid"
DEFAULT_AUDIT_LOG = "audit.log"
DEFAULT_ALERT_LOG = "audit_alerts.log"
DEFAULT_PROXY_PORT = 19998
SCAN_INTERVAL = 2.0
EXFIL_THRESHOLD = 100 * 1024 * 1024
MAX_LOG_SIZE = 100 * 1024 * 1024
MAX_LOG_FILES = 5

ATTACK_SIGNATURES = {
    "command_injection": [
        # Shell metacharacters
        (r'[;|&`$\(\)]', "shell metacharacter"),
        (r'\$\([^)]*\)', "command substitution $()"),
        (r'`[^`]*`', "backtick command substitution"),
        (r'\|\s*(sh|bash|nc|ncat|python|perl|ruby)\b', "pipe to interpreter"),
        (r';\s*(sh|bash|nc|ncat|curl|wget)\b', "semicolon then shell command"),
        (r'&&\s*(sh|bash|nc|ncat|curl|wget)\b', "&& then shell command"),
        (r'\|\|\s*(sh|bash|nc|ncat|curl|wget)\b', "|| then shell command"),
        (r'\bexec\s*\(', "exec() call"),
        (r'\bsystem\s*\(', "system() call"),
        (r'\bpopen\s*\(', "popen() call"),
        (r'\beval\s*\(', "eval() call"),
        # Common injection payloads
        (r';\s*cat\s+/etc/passwd', "etc/passwd via cat"),
        (r';\s*cat\s+/etc/shadow', "etc/shadow via cat"),
        (r';\s*id\s*;', "id command injection"),
        (r';\s*whoami\s*;', "whoami command injection"),
        (r';\s*uname\s+-a', "uname command injection"),
        (r';\s*wget\s+', "wget download injection"),
        (r';\s*curl\s+', "curl download injection"),
        (r';\s*nc\s+', "netcat injection"),
        (r'/bin/sh\s+-c', "sh -c invocation"),
        (r'/bin/bash\s+-c', "bash -c invocation"),
        (r'bash\s+-i\s+>&', "reverse shell bash -i"),
        (r'/dev/tcp/', "bash /dev/tcp reverse shell"),
        (r'/dev/udp/', "bash /dev/udp"),
        (r'mkfifo\s+/tmp/', "mkfifo reverse shell setup"),
    ],
    "sql_injection": [
        (r"'\s*OR\s+'?1'?\s*=\s*'?1", "OR 1=1 classic SQLi"),
        (r"'\s*OR\s+'?1'?\s*=\s*'?1'?\s*--", "OR 1=1 with comment"),
        (r"'\s*OR\s+'?1'?\s*=\s*'?1'?\s*#", "OR 1=1 with hash comment"),
        (r"'\s*OR\s+'?1'?\s*=\s*'?1'?\s*/\*", "OR 1=1 with block comment"),
        (r"\bUNION\s+SELECT\b", "UNION SELECT"),
        (r"\bUNION\s+ALL\s+SELECT\b", "UNION ALL SELECT"),
        (r"--\s*$", "SQL comment at end"),
        (r"--\s*;", "SQL comment semicolon"),
        (r"/\*.*\*/", "SQL block comment"),
        (r"\bxp_cmdshell\b", "MSSQL xp_cmdshell"),
        (r"\bsp_executesql\b", "MSSQL sp_executesql"),
        (r"\bDROP\s+TABLE\b", "DROP TABLE"),
        (r"\bDROP\s+DATABASE\b", "DROP DATABASE"),
        (r"\bINSERT\s+INTO\b", "INSERT INTO"),
        (r"\bDELETE\s+FROM\b", "DELETE FROM"),
        (r"\bUPDATE\s+.*\bSET\b", "UPDATE SET"),
        (r"\bSELECT\s+.*\bFROM\s+information_schema\b", "information_schema access"),
        (r"\bSELECT\s+.*\bFROM\s+mysql\.user\b", "mysql.user access"),
        (r"\bINTO\s+OUTFILE\b", "MySQL INTO OUTFILE"),
        (r"\bINTO\s+DUMPFILE\b", "MySQL INTO DUMPFILE"),
        (r"\bLOAD_FILE\s*\(", "MySQL LOAD_FILE"),
        (r"\bCONCAT\s*\(", "MySQL CONCAT"),
        (r"\bSLEEP\s*\(\s*\d+\s*\)", "SLEEP() time-based SQLi"),
        (r"\bBENCHMARK\s*\(", "BENCHMARK() time-based SQLi"),
        (r"\bWAITFOR\s+DELAY\b", "MSSQL WAITFOR DELAY"),
        (r"'\s*;\s*", "semicolon after quote"),
    ],
    "path_traversal": [
        (r'\.\./', "../ directory traversal"),
        (r'\.\.\\', "..\\ directory traversal"),
        (r'%2e%2e%2f', "%2e%2e%2f encoded traversal"),
        (r'%2e%2e/', "%2e%2e/ encoded traversal"),
        (r'..%2f', "..%2f encoded traversal"),
        (r'..%5c', "..%5c encoded traversal"),
        (r'%2e%2e%5c', "%2e%2e%5c encoded traversal"),
        (r'\.\.%c0%af', "UTF-8 overlong traversal"),
        (r'\.\.%c1%9c', "UTF-8 overlong traversal"),
        (r'....//', "double dot slash bypass"),
        (r'....\\\\', "double dot backslash bypass"),
        (r'\x00', "null byte injection"),
        (r'%00', "encoded null byte"),
        (r'/etc/passwd', "/etc/passwd access"),
        (r'/etc/shadow', "/etc/shadow access"),
        (r'/etc/sudoers', "/etc/sudoers access"),
        (r'/root/\.', "/root/ directory access"),
        (r'/home/[^/]+/\.ssh', "SSH directory access"),
        (r'authorized_keys', "authorized_keys access"),
        (r'/proc/self/environ', "/proc/self/environ access"),
        (r'/proc/self/cmdline', "/proc/self/cmdline access"),
    ],
    "xss": [
        (r'<script', "<script> tag"),
        (r'</script>', "</script> tag"),
        (r'javascript:', "javascript: protocol"),
        (r'onerror\s*=', "onerror event handler"),
        (r'onload\s*=', "onload event handler"),
        (r'onclick\s*=', "onclick event handler"),
        (r'onmouseover\s*=', "onmouseover event handler"),
        (r'onfocus\s*=', "onfocus event handler"),
        (r'onblur\s*=', "onblur event handler"),
        (r'<iframe', "<iframe> tag"),
        (r'<object', "<object> tag"),
        (r'<embed', "<embed> tag"),
        (r'<svg\s+onload', "<svg onload> XSS"),
        (r'<img\s+[^>]*onerror', "<img onerror> XSS"),
        (r'document\.cookie', "document.cookie access"),
        (r'document\.location', "document.location access"),
        (r'window\.location', "window.location access"),
        (r'eval\s*\(', "eval() XSS"),
        (r'String\.fromCharCode', "String.fromCharCode obfuscation"),
        (r'\\x[0-9a-f]{2}', "hex escape sequence"),
    ],
    "ssrf": [
        (r'http://127\.0\.0\.1', "localhost HTTP access"),
        (r'http://localhost', "localhost HTTP access"),
        (r'http://0\.0\.0\.0', "0.0.0.0 HTTP access"),
        (r'http://\[::1\]', "IPv6 localhost access"),
        (r'http://169\.254\.169\.254', "AWS metadata endpoint"),
        (r'http://metadata\.google\.internal', "GCP metadata endpoint"),
        (r'http://169\.254\.169\.254/computeMetadata', "GCP metadata v1"),
        (r'http://100\.100\.100\.200', "Alibaba Cloud metadata"),
        (r'http://metadata\.azure\.com', "Azure metadata endpoint"),
        (r'file://', "file:// protocol"),
        (r'gopher://', "gopher:// protocol"),
        (r'dict://', "dict:// protocol"),
        (r'ftp://', "ftp:// protocol"),
        (r'smb://', "smb:// protocol"),
        (r'ldap://', "ldap:// protocol"),
        (r'http://10\.\d+\.\d+\.\d+', "private 10.x.x.x access"),
        (r'http://192\.168\.\d+\.\d+', "private 192.168.x.x access"),
        (r'http://172\.(1[6-9]|2[0-9]|3[01])\.', "private 172.16-31.x.x access"),
    ],
    "credential_exfil": [
        (r'Bearer\s+[A-Za-z0-9._-]{20,}', "Bearer token in request"),
        (r'api[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9]{16,}', "API key"),
        (r'authorization\s*:\s*bearer', "Authorization header"),
        (r'x-api-key\s*:', "X-API-Key header"),
        (r'password\s*[=:]\s*["\']?[^\s"\']{8,}', "password field"),
        (r'passwd\s*[=:]\s*["\']?[^\s"\']{8,}', "passwd field"),
        (r'secret\s*[=:]\s*["\']?[A-Za-z0-9]{16,}', "secret field"),
        (r'token\s*[=:]\s*["\']?[A-Za-z0-9]{16,}', "token field"),
        (r'jwt\s*[=:]\s*["\']?ey[A-Za-z0-9._-]+', "JWT token"),
        (r'BEGIN\s+[A-Z\s]+PRIVATE\s+KEY', "private key in traffic"),
        (r'AKIA[0-9A-Z]{16}', "AWS access key ID"),
        (r'gh[pu]_[A-Za-z0-9]{36,}', "GitHub token"),
        (r'xox[baprs]-[A-Za-z0-9-]+', "Slack token"),
    ],
    "reverse_shell": [
        (r'bash\s+-i\s+>&\s*/dev/tcp/', "bash reverse shell /dev/tcp"),
        (r'sh\s+-i\s+>&\s*/dev/tcp/', "sh reverse shell /dev/tcp"),
        (r'nc\s+-e\s+/bin/', "netcat -e reverse shell"),
        (r'ncat\s+-e\s+/bin/', "ncat -e reverse shell"),
        (r'python\s+-c\s+.*socket', "python reverse shell"),
        (r'perl\s+-e\s+.*socket', "perl reverse shell"),
        (r'ruby\s+-e\s+.*socket', "ruby reverse shell"),
        (r'php\s+-r\s+.*socket', "php reverse shell"),
        (r'/dev/tcp/\d+\.\d+\.\d+\.\d+/', "/dev/tcp IP address"),
        (r'/dev/udp/\d+\.\d+\.\d+\.\d+/', "/dev/udp IP address"),
        (r'mknod\s+/tmp/', "mknod reverse shell"),
        (r'mkfifo\s+/tmp/', "mkfifo reverse shell"),
    ],
    "suspicious_file_access": [
        r'/etc/passwd',
        r'/etc/shadow',
        r'/etc/sudoers',
        r'/etc/ssh/',
        r'/root/\.ssh/',
        r'/home/[^/]+/\.ssh/',
        r'authorized_keys',
        r'/proc/self/environ',
        r'/proc/self/cmdline',
        r'/proc/self/mem',
        r'/boot/grub',
        r'/var/log/auth\.log',
        r'/var/log/secure',
        r'\.bash_history',
        r'\.mysql_history',
        r'\.psql_history',
        r'/tmp/\.\w+',  # hidden files in /tmp
        r'/dev/shm/[^/]',  # files in /dev/shm (often used by malware)
    ],
    "suspicious_process": [
        r'^/bin/sh\b',
        r'^/bin/bash\b',
        r'^sh\b',
        r'^bash\b',
        r'^nc\b',
        r'^ncat\b',
        r'^netcat\b',
        r'^telnet\b',
        r'^ssh\b',
        r'^scp\b',
        r'^curl\b',
        r'^wget\b',
        r'^python\s+-c\b',
        r'^perl\s+-e\b',
        r'^ruby\s+-e\b',
        r'^chmod\s+\+x\b',
        r'^chown\s+root\b',
        r'^kill\s+-9\b',
        r'^pkill\b',
    ],
}

# Suspicious outbound IPs (known bad ranges) - empty by default
# Add specific IPs to watch for
SUSPICIOUS_IPS = set()

# Expected outbound ports (everything else is suspicious)
EXPECTED_PORTS = {80, 443, 89, 53}

# Expected CDN domains (whitelist for outbound connections)
EXPECTED_DOMAINS = {
    'akamaized.net', 'akamai.net', 'rogers.com', 'nordvpn.com',
    'surfshark.com', 'movetv.com', 'sling.com', 'pcdn03.cssott.com',
    'w3.org', 'golang.org', 'github.com', 'momentjs.com',
    'netskrt.live.pv-cdn.net', 'lpnba.akamaized.net',
    'qp-pldt-live-bpk-02-prod.akamaized.net', 'g001-live-us-cmaf-prd-fy.pcdn03.cssott.com',
    'live-d-01-rogers-cc-prd.akamaized.net', 'live-d-02-rogers-uw-prd.akamaized.net',
    'p-cdn1-a-cg14-linear-cbd46b77.movetv.com',
    'p-cdn4-a-cg14-linear-cbd46b77.movetv.com',
}

class AuditLogger:
    """Thread-safe audit logger with rotation."""

    def __init__(self, log_path, alert_path, max_size=MAX_LOG_SIZE, max_files=MAX_LOG_FILES):
        self.log_path = Path(log_path)
        self.alert_path = Path(alert_path)
        self.max_size = max_size
        self.max_files = max_files
        self.lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.alert_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate(self, path):
        if not path.exists() or path.stat().st_size < self.max_size:
            return
        for i in range(self.max_files - 1, 0, -1):
            old = path.with_suffix(f'.{i}{path.suffix}')
            new = path.with_suffix(f'.{i+1}{path.suffix}')
            if old.exists():
                old.rename(new)
        path.rename(path.with_suffix(f'.1{path.suffix}'))

    def log(self, event_type, severity, source, details, raw_data=None):
        """Log a security event."""
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": timestamp,
            "type": event_type,
            "severity": severity,  # INFO, LOW, MEDIUM, HIGH, CRITICAL
            "source": source,      # http, proc, net, file, child
            "details": details,
        }
        if raw_data:
            entry["raw"] = raw_data[:1000]  # cap raw data

        line = json.dumps(entry, ensure_ascii=False)
        with self.lock:
            self._rotate(self.log_path)
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
            # High-severity events also go to alerts log
            if severity in ('HIGH', 'CRITICAL'):
                self._rotate(self.alert_path)
                with open(self.alert_path, 'a', encoding='utf-8') as f:
                    f.write(line + '\n')

        # Print to stdout with color
        color = {
            'INFO': '\033[37m',
            'LOW': '\033[36m',
            'MEDIUM': '\033[33m',
            'HIGH': '\033[31m',
            'CRITICAL': '\033[1;31m',
        }.get(severity, '\033[0m')
        reset = '\033[0m'
        print(f"{color}[{timestamp}] {severity:8s} {event_type:25s} {source:8s}{reset} {details}")
        return entry


class AttackDetector:
    """Detect attacks in strings and URLs."""

    def __init__(self, logger):
        self.logger = logger
        self.compiled = {}
        for category, patterns in ATTACK_SIGNATURES.items():
            compiled = []
            for p in patterns:
                if isinstance(p, tuple):
                    compiled.append((re.compile(p[0], re.IGNORECASE), p[1]))
                else:
                    # bare pattern (no description) used by suspicious_file_access/process
                    compiled.append((re.compile(p, re.IGNORECASE), category))
            self.compiled[category] = compiled

    def scan_string(self, text, source='http', context=''):
        """Scan a string for attack patterns. Returns list of matches."""
        if not text:
            return []
        text_str = text if isinstance(text, str) else text.decode('utf-8', errors='replace')
        matches = []

        for category, patterns in self.compiled.items():
            if category in ('suspicious_file_access', 'suspicious_process'):
                continue  # these are handled separately
            for regex, desc in patterns:
                for m in regex.finditer(text_str):
                    severity = self._severity(category)
                    details = f"{desc}: matched '{m.group()[:80]}' in {context}"
                    self.logger.log(f"attack_{category}", severity, source, details, text_str[:500])
                    matches.append((category, desc, m.group()))

        return matches

    def _severity(self, category):
        severities = {
            'command_injection': 'CRITICAL',
            'sql_injection': 'HIGH',
            'path_traversal': 'HIGH',
            'xss': 'MEDIUM',
            'ssrf': 'HIGH',
            'credential_exfil': 'HIGH',
            'reverse_shell': 'CRITICAL',
        }
        return severities.get(category, 'MEDIUM')

    def scan_url(self, url, source='http'):
        """Scan a URL for attacks."""
        return self.scan_string(url, source, f'URL: {url[:100]}')

    def scan_headers(self, headers, source='http'):
        """Scan HTTP headers for attacks."""
        for key, value in headers.items():
            self.scan_string(value, source, f'header {key}')

    def scan_body(self, body, source='http'):
        """Scan HTTP body for attacks."""
        if isinstance(body, bytes):
            try:
                body = body.decode('utf-8', errors='replace')
            except:
                return []
        return self.scan_string(body, source, 'request body')


class ProcessMonitor:
    """Monitor a process via /proc filesystem."""

    def __init__(self, pid, logger, detector):
        self.pid = pid
        self.logger = logger
        self.detector = detector
        self.prev_io = None
        self.prev_children = set()
        self.prev_fds = set()
        self.prev_connections = set()
        self.running = True

    def _read_file(self, path):
        try:
            with open(path) as f:
                return f.read()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return None

    def _get_children(self):
        """Get child process PIDs."""
        children = set()
        try:
            task_dirs = os.listdir(f'/proc/{self.pid}/task')
        except (FileNotFoundError, ProcessLookupError):
            return children
        for tid in task_dirs:
            content = self._read_file(f'/proc/{self.pid}/task/{tid}/children')
            if content:
                for pid_str in content.split():
                    try:
                        children.add(int(pid_str))
                    except ValueError:
                        pass
        return children

    def _get_fds(self):
        """Get open file descriptors."""
        fds = set()
        try:
            fd_list = os.listdir(f'/proc/{self.pid}/fd')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return fds
        for fd in fd_list:
            try:
                link = os.readlink(f'/proc/{self.pid}/fd/{fd}')
                fds.add((fd, link))
            except (OSError, PermissionError):
                pass
        return fds

    def _get_connections(self):
        """Get network connections from /proc/<pid>/net/tcp and tcp6."""
        conns = set()
        for proto in ('tcp', 'tcp6'):
            content = self._read_file(f'/proc/{self.pid}/net/{proto}')
            if not content:
                continue
            for line in content.split('\n')[1:]:  # skip header
                parts = line.split()
                if len(parts) < 4:
                    continue
                local = parts[1]
                remote = parts[2]
                state = parts[3]
                if state != '01':  # ESTABLISHED
                    continue
                # Parse address:port
                try:
                    if proto == 'tcp':
                        # IPv4: hex IP:port
                        ip_hex, port_hex = local.split(':')
                        ip = socket.inet_ntoa(struct.pack('<I', int(ip_hex, 16)))
                        port = int(port_hex, 16)
                        r_ip_hex, r_port_hex = remote.split(':')
                        r_ip = socket.inet_ntoa(struct.pack('<I', int(r_ip_hex, 16)))
                        r_port = int(r_port_hex, 16)
                    else:
                        # IPv6: 32 hex chars : port
                        ip_hex, port_hex = local.split(':')
                        ip_bytes = bytes.fromhex(ip_hex)
                        ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
                        port = int(port_hex, 16)
                        r_ip_hex, r_port_hex = remote.split(':')
                        r_ip_bytes = bytes.fromhex(r_ip_hex)
                        r_ip = socket.inet_ntop(socket.AF_INET6, r_ip_bytes)
                        r_port = int(r_port_hex, 16)
                    conns.add((r_ip, r_port, proto))
                except (ValueError, struct.error, OSError):
                    pass
        return conns

    def _get_io(self):
        """Get process I/O stats."""
        content = self._read_file(f'/proc/{self.pid}/io')
        if not content:
            return None
        io = {}
        for line in content.split('\n'):
            if ':' in line:
                key, _, val = line.partition(':')
                try:
                    io[key.strip()] = int(val.strip())
                except ValueError:
                    pass
        return io

    def _get_child_cmdline(self, child_pid):
        """Get command line of a child process."""
        content = self._read_file(f'/proc/{child_pid}/cmdline')
        if not content:
            return ''
        return content.replace('\x00', ' ').strip()

    def check_suspicious_files(self, fds):
        """Check open FDs for suspicious file access."""
        for fd, link in fds:
            for pattern in ATTACK_SIGNATURES['suspicious_file_access']:
                if re.search(pattern, link, re.IGNORECASE):
                    self.logger.log(
                        'suspicious_file_access', 'HIGH', 'file',
                        f'Process opened suspicious file: {link} (fd={fd})'
                    )

    def check_suspicious_children(self, children):
        """Check for suspicious child processes."""
        for child_pid in children - self.prev_children:
            cmdline = self._get_child_cmdline(child_pid)
            if not cmdline:
                continue
            for pattern in ATTACK_SIGNATURES['suspicious_process']:
                if re.match(pattern, cmdline, re.IGNORECASE):
                    self.logger.log(
                        'suspicious_process', 'CRITICAL', 'child',
                        f'Suspicious child process spawned: PID={child_pid} cmd={cmdline[:200]}'
                    )
            # Log all new child processes
            self.logger.log(
                'child_process', 'INFO', 'child',
                f'New child process: PID={child_pid} cmd={cmdline[:200]}'
            )

    def check_connections(self, conns):
        """Check for suspicious network connections."""
        for ip, port, proto in conns - self.prev_connections:
            # Check suspicious IPs
            if ip in SUSPICIOUS_IPS:
                self.logger.log(
                    'suspicious_connection', 'HIGH', 'net',
                    f'Connection to known-suspicious IP: {ip}:{port} ({proto})'
                )
            # Check unexpected ports
            if port not in EXPECTED_PORTS:
                self.logger.log(
                    'unexpected_port', 'MEDIUM', 'net',
                    f'Connection to unexpected port: {ip}:{port} ({proto})'
                )
            # Check for private IP access (potential SSRF)
            try:
                parts = ip.split('.')
                if len(parts) == 4:
                    first = int(parts[0])
                    if first == 10 or (first == 172 and 16 <= int(parts[1]) <= 31) or \
                       (first == 192 and int(parts[1]) == 168) or ip == '127.0.0.1':
                        self.logger.log(
                            'ssrf_internal', 'HIGH', 'net',
                            f'Connection to internal IP: {ip}:{port} ({proto})'
                        )
            except (ValueError, IndexError):
                pass

            # Log all new connections
            self.logger.log(
                'connection', 'INFO', 'net',
                f'New connection: {ip}:{port} ({proto})'
            )

    def check_exfil(self, io):
        """Check for high-volume data transfer (exfiltration)."""
        if not self.prev_io or not io:
            return
        bytes_sent_delta = io.get('write_bytes', 0) - self.prev_io.get('write_bytes', 0)
        if bytes_sent_delta > EXFIL_THRESHOLD:
            self.logger.log(
                'potential_exfil', 'HIGH', 'net',
                f'High outbound transfer: {bytes_sent_delta / 1024 / 1024:.1f} MB in {SCAN_INTERVAL}s interval'
            )

    def scan(self):
        """Run one scan cycle."""
        if not os.path.exists(f'/proc/{self.pid}'):
            self.logger.log('process_exit', 'HIGH', 'proc', f'Process {self.pid} no longer exists')
            self.running = False
            return

        children = self._get_children()
        fds = self._get_fds()
        conns = self._get_connections()
        io = self._get_io()

        self.check_suspicious_files(fds)
        self.check_suspicious_children(children)
        self.check_connections(conns)
        self.check_exfil(io)

        self.prev_children = children
        self.prev_fds = fds
        self.prev_connections = conns
        self.prev_io = io

    def run(self):
        """Main monitoring loop."""
        self.logger.log('monitor_start', 'INFO', 'proc', f'Started monitoring PID {self.pid}')
        while self.running:
            try:
                self.scan()
            except Exception as e:
                self.logger.log('monitor_error', 'LOW', 'proc', f'Scan error: {e}')
            time.sleep(SCAN_INTERVAL)


# HTTP Proxy

class ProxyRequestHandler(BaseHTTPRequestHandler):
    """HTTP proxy handler that scans all requests for attacks."""

    detector = None
    logger = None
    target_host = '127.0.0.1'
    target_port = 19999

    def log_message(self, format, *args):
        pass  # suppress default logging

    def _forward(self, method):
        """Forward request to target and scan for attacks."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        self.logger.log('http_request', 'INFO', 'http',
                        f'{method} {self.path} from {self.client_address[0]}')
        self.detector.scan_url(self.path, 'http')
        self.detector.scan_headers(dict(self.headers), 'http')
        if body:
            self.detector.scan_body(body, 'http')

        
        try:
            conn = http.client.HTTPConnection(self.target_host, self.target_port, timeout=30)
            headers = dict(self.headers)
            headers['Host'] = f'{self.target_host}:{self.target_port}'
            conn.request(method, self.path, body=body, headers=headers)
            response = conn.getresponse()
            resp_body = response.read()

            self.detector.scan_body(resp_body, 'http_resp')

            
            self.send_response(response.status)
            for key, val in response.getheaders():
                if key.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(key, val)
            self.send_header('Content-Length', str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            conn.close()
        except Exception as e:
            self.logger.log('proxy_error', 'MEDIUM', 'http', f'Forward error: {e}')
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b'Bad Gateway')

    def do_GET(self):
        self._forward('GET')

    def do_POST(self):
        self._forward('POST')

    def do_PUT(self):
        self._forward('PUT')

    def do_DELETE(self):
        self._forward('DELETE')

    def do_PATCH(self):
        self._forward('PATCH')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.end_headers()


class ThreadedProxyServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP proxy server for concurrent request handling."""
    daemon_threads = True
    allow_reuse_address = True


def run_proxy(port, target_host, target_port, detector, logger):
    """Run the HTTP proxy server."""
    ProxyRequestHandler.detector = detector
    ProxyRequestHandler.logger = logger
    ProxyRequestHandler.target_host = target_host
    ProxyRequestHandler.target_port = target_port
    server = ThreadedProxyServer(('0.0.0.0', port), ProxyRequestHandler)
    logger.log('proxy_start', 'INFO', 'http',
               f'Proxy listening on 0.0.0.0:{port}, forwarding to {target_host}:{target_port}')
    server.serve_forever()


# File watcher

class FileWatcher:
    """Watch key files for unauthorized changes."""

    def __init__(self, logger, watch_paths=None):
        self.logger = logger
        self.watch_paths = watch_paths or [
            'keys.txt',
            'providers/sample.cfg',
            'o11.cfg',
            'logs/',
            'hls/',
        ]
        self.prev_state = {}

    def _scan_path(self, path):
        """Get current state of a path (file hash or dir listing)."""
        import hashlib
        if os.path.isfile(path):
            try:
                with open(path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            except (PermissionError, FileNotFoundError):
                return None
        elif os.path.isdir(path):
            result = {}
            try:
                for entry in os.listdir(path):
                    full = os.path.join(path, entry)
                    if os.path.isfile(full):
                        try:
                            with open(full, 'rb') as f:
                                result[entry] = hashlib.md5(f.read()).hexdigest()
                        except (PermissionError, FileNotFoundError):
                            pass
                    elif os.path.isdir(full):
                        result[entry] = 'dir'
            except (PermissionError, FileNotFoundError):
                pass
            return result
        return None

    def scan(self):
        """Scan watched paths for changes."""
        for path in self.watch_paths:
            current = self._scan_path(path)
            if path not in self.prev_state:
                self.prev_state[path] = current
                continue
            if current != self.prev_state[path]:
                if os.path.isfile(path):
                    self.logger.log('file_change', 'MEDIUM', 'file',
                                    f'File changed: {path}')
                elif os.path.isdir(path):
                    old = self.prev_state[path] or {}
                    new = current or {}
                    for f in set(new.keys()) - set(old.keys()):
                        self.logger.log('file_create', 'LOW', 'file',
                                        f'New file in {path}: {f}')
                    for f in set(old.keys()) - set(new.keys()):
                        self.logger.log('file_delete', 'LOW', 'file',
                                        f'File deleted from {path}: {f}')
                    for f in set(new.keys()) & set(old.keys()):
                        if old[f] != new[f] and old[f] != 'dir' and new[f] != 'dir':
                            self.logger.log('file_modify', 'MEDIUM', 'file',
                                            f'File modified in {path}: {f}')
                self.prev_state[path] = current

    def run(self):
        while True:
            try:
                self.scan()
            except Exception as e:
                self.logger.log('watcher_error', 'LOW', 'file', f'Watch error: {e}')
            time.sleep(5)


# Main

def find_o11_pid():
    """Auto-detect the o11 PID."""
    name_patterns = ['o11pro', 'o11pro']

    for pattern in name_patterns:
        try:
            result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                if pids:
                    return int(pids[0])
        except (FileNotFoundError, ValueError):
            pass

    for pid_file in (DEFAULT_PID_FILE, '/tmp/o11e2e/pid'):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
                if os.path.exists(f'/proc/{pid}'):
                    return pid
        except (FileNotFoundError, ValueError):
            pass

    for entry in os.listdir('/proc'):
        if not entry.isdigit():
            continue
        try:
            with open(f'/proc/{entry}/cmdline', 'rb') as f:
                cmdline = f.read().decode('utf-8', errors='replace')
            for pattern in name_patterns:
                if pattern in cmdline:
                    return int(entry)
        except (FileNotFoundError, PermissionError):
            pass

    return None


def main():
    parser = argparse.ArgumentParser(description='Security monitor for o11pro')
    parser.add_argument('--pid', type=int, help='PID of o11 process to monitor (auto-detected if omitted)')
    parser.add_argument('--log', default=DEFAULT_AUDIT_LOG, help='Audit log file path')
    parser.add_argument('--alerts', default=DEFAULT_ALERT_LOG, help='Alerts log file path (HIGH/CRITICAL only)')
    parser.add_argument('--proxy-mode', action='store_true', help='Run as HTTP proxy (intercepts all API traffic)')
    parser.add_argument('--proxy-port', type=int, default=DEFAULT_PROXY_PORT, help='Proxy listen port')
    parser.add_argument('--target-port', type=int, default=19999, help='Target port (the real o11 API)')
    parser.add_argument('--no-proc', action='store_true', help='Disable process monitoring')
    parser.add_argument('--no-files', action='store_true', help='Disable file watching')
    parser.add_argument('--once', action='store_true', help='Run one scan and exit')
    args = parser.parse_args()

    logger = AuditLogger(args.log, args.alerts)
    detector = AttackDetector(logger)

    logger.log('startup', 'INFO', 'main', f'Security monitor v{VERSION} starting')
    logger.log('startup', 'INFO', 'main', f'Audit log: {args.log}')
    logger.log('startup', 'INFO', 'main', f'Alerts log: {args.alerts}')

    
    if args.proxy_mode:
        proxy_thread = threading.Thread(
            target=run_proxy,
            args=(args.proxy_port, '127.0.0.1', args.target_port, detector, logger),
            daemon=True
        )
        proxy_thread.start()
        logger.log('startup', 'INFO', 'main',
                   f'Proxy mode active point your client to :{args.proxy_port} instead of :{args.target_port}')

    pid = args.pid or find_o11_pid()
    if not pid:
        logger.log('startup', 'ERROR', 'main', 'Could not find o11 process. Use --pid to specify.')
        if not args.proxy_mode:
            sys.exit(1)
        logger.log('startup', 'INFO', 'main', 'Running in proxy-only mode (no process monitoring)')
    else:
        logger.log('startup', 'INFO', 'main', f'Monitoring PID {pid}')

    if pid and not args.no_proc:
        proc_monitor = ProcessMonitor(pid, logger, detector)
        if args.once:
            proc_monitor.scan()
        else:
            proc_thread = threading.Thread(target=proc_monitor.run, daemon=True)
            proc_thread.start()

    if not args.no_files:
        watcher = FileWatcher(logger)
        if args.once:
            watcher.scan()
        else:
            watch_thread = threading.Thread(target=watcher.run, daemon=True)
            watch_thread.start()

    if args.once:
        logger.log('shutdown', 'INFO', 'main', 'One-shot scan complete')
        return

    modes = []
    if args.proxy_mode:
        modes.append(f'proxy on :{args.proxy_port}')
    if pid and not args.no_proc:
        modes.append(f'process monitor (PID {pid})')
    if not args.no_files:
        modes.append('file watcher')

    logger.log('startup', 'INFO', 'main',
               f'Monitor running {", ".join(modes) or "no active modules"}. Press Ctrl+C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.log('shutdown', 'INFO', 'main', 'Shutting down (Ctrl+C)')


if __name__ == '__main__':
    main()