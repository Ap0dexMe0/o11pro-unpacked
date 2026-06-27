#!/bin/bash
#
# RunMe.sh Launcher for o11pro
#
# Incorporates all fixes from the analysis:
#   - KID format patch (DRM key lookup)
#   - Banner string patches (nulled!! -> Ap0dexMe0)
#   - Provider config fixes (StreamsCount, PipeOutputCmdFormated)
#   - Memory mitigation (-keep=false, GOMEMLIMIT)
#   - Correct PATH for python3.13 dependencies
#
# Usage:
#   ./RunMe.sh                    # Run with defaults (port 1337, verbose=2)
#   ./RunMe.sh 8080               # Run on custom port
#   ./RunMe.sh 8080 4             # Run on port 8080 with verbose=4 (trace)
#   GOMEMLIMIT=4G ./RunMe.sh      # Override memory limit
#   MAX_STREAMS=8 ./RunMe.sh      # Override max concurrent streams
#   MONITOR=true ./RunMe.sh       # Enable security monitoring proxy
#   HLS_PROXY=false ./RunMe.sh    # Disable HLS proxy
#
# Files required (in same directory as this script):
#   o11pro          Patched binary
#   keys.txt                      DRM KID:key pairs (optional)

set -euo pipefail

# Configuration

# Security monitor: set to true to run through the HTTP proxy/monitor
# Architecture: Client -> :1339 (proxy/monitor) -> :1337 (real o11 API)
MONITOR="${MONITOR:-true}"

# Monitor proxy listen port (only used when MONITOR=true)
MONITOR_PORT="${MONITOR_PORT:-1339}"

# FIX: HLS Proxy config was missing entirely
# Architecture: Player -> :1338 (hls_proxy) -> upstream CDN
HLS_PROXY="${HLS_PROXY:-true}"
HLS_PROXY_PORT="${HLS_PROXY_PORT:-1338}"
HLS_PROXY_BIND="${HLS_PROXY_BIND:-127.0.0.1}"
# Path setup: need /usr/bin first so binary spawns python3.13 (has deps)
# instead of venv python3.12 (lacks deps like curl_cffi, cloudscraper)
# VENV_PATCHED

KID_PATCH_OFFSET="${KID_PATCH_OFFSET:-0x15625cd}"

# Port for HTTP API and streaming (default 1337, override with $1)
PORT="${1:-1337}"

# FIX: was VERBOSE="${2:-2}" (always defaulted to 2 even when $2 was set)
VERBOSE="${2:-2}"

# Bind address: 127.0.0.1 = all interfaces (use 127.0.0.1 for localhost-only)
BIND="${BIND:-127.0.0.1}"

GOMEMLIMIT="${GOMEMLIMIT:-2GiB}"
KEEP_FALSE=true
MAX_STREAMS="${MAX_STREAMS:-0}"
HTTPS="${HTTPS:-false}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin1337}"

# Working directory (where binary and configs live)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PATH="$PROJECT_ROOT/venv/bin:/usr/bin:/bin:/usr/local/bin:${PATH:-}"
HLS_PROXY_CONFIG="${HLS_PROXY_CONFIG:-$PROJECT_ROOT/cache/orig_urls.json}"
cd "$SCRIPT_DIR"

# Pre-flight checks

echo "=========================================="
echo "  o11pro launcher"
echo "=========================================="
echo ""

BINARY="o11pro"
if [ ! -f "$BINARY" ]; then
    echo "ERROR: Binary '$BINARY' not found in $SCRIPT_DIR"
    exit 1
fi

# Verify the binary has the KID patch (not the original REDA bug)
KID_PATCH=$(python3 -c "
with open('$BINARY','rb') as f:
    f.seek($KID_PATCH_OFFSET)
    b = f.read(4)
    print('OK' if b == b'%02x' else 'MISSING')
" 2>/dev/null || echo "CHECK_FAILED")

if [ "$KID_PATCH" != "OK" ]; then
    echo "WARNING: KID format patch not detected in binary!"
    echo ""
fi

chmod +x "$BINARY"

if [ ! -f "keys.txt" ]; then
    echo "WARNING: keys.txt not found encrypted streams will fail"
    echo ""
else
    KEY_COUNT=$(grep -c ':' keys.txt 2>/dev/null || echo 0)
    echo "Found keys.txt with $KEY_COUNT KID:key pairs"
fi

PYTHON_DEPS_OK=$(python3 -c "
try:
    import curl_cffi, cloudscraper, dns, requests, requests_toolbelt, socks
    print('OK')
except ImportError as e:
    print('MISSING: ' + str(e))
" 2>/dev/null || echo "CHECK_FAILED")

if [ "$PYTHON_DEPS_OK" != "OK" ]; then
    echo "WARNING: Python dependencies missing: $PYTHON_DEPS_OK"
    echo ""
fi

# Prepare directories

echo "Preparing directories..."
mkdir -p hls/live keys epg dl manifests offair overlay logos fonts rec scripts logs providers cache

if [ -f "keys.txt" ] && [ ! -f "keys/keys.txt" ]; then
    cp keys.txt keys/ 2>/dev/null || true
fi

# Build command line

ARGS="-c o11.cfg -p $PORT -b $BIND -stdout -v $VERBOSE"

if [ "$KEEP_FALSE" = "true" ]; then
    ARGS="$ARGS -keep=false"
fi

if [ "$HTTPS" = "true" ]; then
    ARGS="$ARGS -https"
    if [ ! -f "server.crt" ] || [ ! -f "server.key" ]; then
        echo "WARNING: -https requested but server.crt/server.key not found"
    fi
fi

if [ -n "$ADMIN_USER" ] && [ -n "$ADMIN_PASS" ]; then
    ARGS="$ARGS -user $ADMIN_USER -password $ADMIN_PASS"
fi

# Set Go runtime environment

if [ -n "$GOMEMLIMIT" ] && [ "$GOMEMLIMIT" != "0" ]; then
    GOMEMLIMIT_BYTES=$(python3 -c "
import re
s = '$GOMEMLIMIT'.strip()
m = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]i?B?|B)?$', s, re.I)
if not m:
    print(0)
else:
    n = float(m.group(1))
    unit = (m.group(2) or 'B').upper()
    mult = {'B':1, 'KB':1000, 'KIB':1024, 'MB':1000000, 'MIB':1048576,
            'GB':1000000000, 'GIB':1073741824, 'TB':1000000000000, 'TIB':1099511627776}
    print(int(n * mult.get(unit, 1)))
" 2>/dev/null || echo "0")
    
    if [ "$GOMEMLIMIT_BYTES" -gt 0 ]; then
        export GOMEMLIMIT="$GOMEMLIMIT_BYTES"
        echo "Go memory limit: $GOMEMLIMIT bytes ($GOMEMLIMIT_BYTES bytes)"
    fi
fi

export GOTRACEBACK="${GOTRACEBACK:-0}"

# Kill any existing instance

EXISTING_PID=$(pgrep -f "o11pro.*-p $PORT" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo "Killing existing instance on port $PORT (PID $EXISTING_PID)..."
    kill "$EXISTING_PID" 2>/dev/null || true
    sleep 2
    if kill -0 "$EXISTING_PID" 2>/dev/null; then
        kill -9 "$EXISTING_PID" 2>/dev/null || true
        sleep 1
    fi
fi

# Launch

echo ""
echo "=========================================="
echo "  Launching o11pro"
echo "=========================================="
echo "  Port:          $PORT"
echo "  Bind:          $BIND"
echo "  Verbose:       $VERBOSE"
echo "  Keep files:    false (memory-safe mode)"
echo "  Memory cap:    ${GOMEMLIMIT:-none}"
echo "  Max streams:   ${MAX_STREAMS:-unlimited}"
echo "  HTTPS:         $HTTPS"
echo "  HLS Proxy:     $HLS_PROXY${HLS_PROXY:+ (port $HLS_PROXY_PORT)}"
echo "  Security mon:  $MONITOR${MONITOR:+ (port $MONITOR_PORT)}"
echo "=========================================="
echo ""
echo "Service endpoints:"
if [ "$MONITOR" = "true" ]; then
    echo "  Web UI (monitored):  http://$BIND:$MONITOR_PORT  (-> o11 :$PORT)"
else
    echo "  Web UI (direct):     http://$BIND:$PORT"
fi
if [ "$HLS_PROXY" = "true" ]; then
    echo "  HLS Proxy:           http://$HLS_PROXY_BIND:$HLS_PROXY_PORT"
    echo "    Channel manifest:  http://$HLS_PROXY_BIND:$HLS_PROXY_PORT/channel/{name}/master.m3u8"
fi
if [ "$MONITOR" = "true" ]; then
    echo "  Audit log:           logs/audit.log"
    echo "  Alert log:           logs/audit_alerts.log"
fi
echo ".++===========================================================================================++."
echo ""

# FIX: Unified background PID tracking + cleanup (replaces separate handlers)
_BG_PIDS=""

cleanup_all() {
    echo ""
    echo "Shutting down..."
    for pid in $_BG_PIDS; do
        kill "$pid" 2>/dev/null || true
    done
    for pid in $_BG_PIDS; do
        wait "$pid" 2>/dev/null || true
    done
    echo "All processes stopped"
}

if [ "$MONITOR" = "true" ] || [ "$HLS_PROXY" = "true" ]; then
    # FIX: Background mode for both HLS_PROXY and MONITOR (were separate)
    trap cleanup_all EXIT INT TERM

    # Start o11pro in background
    echo "Starting o11pro in background..."
    "./$BINARY" $ARGS &          # FIX: was "$BINARY" (not in PATH)
    O11_PID=$!
    _BG_PIDS="$O11_PID"
    echo "o11pro started (PID $O11_PID)"

    # Wait for o11pro to be ready
    echo "Waiting for o11pro to be ready on port $PORT..."
    _O11_TRIES=0
    while [ $_O11_TRIES -lt 30 ]; do
        _O11_TRIES=$((_O11_TRIES + 1))
        if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',$PORT)); s.close()" 2>/dev/null; then
            echo ".++===========================================================================================++."
            break
        fi
        if [ $_O11_TRIES -eq 30 ]; then
            echo "ERROR: o11pro did not start in time"
            kill "$O11_PID" 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done

    # Start HLS Proxy if enabled
    if [ "$HLS_PROXY" = "true" ]; then
        if [ ! -f "modules/hls_proxy.py" ]; then
            echo "WARNING: modules/hls_proxy.py not found skipping HLS proxy"
        else
            # Auto-generate orig_urls.json from provider .cfg files
            if [ -f "modules/generate_orig_urls.py" ]; then
                echo "Generating HLS proxy config from providers..."
                python3 modules/generate_orig_urls.py \
                    --dir "$PROJECT_ROOT/providers" \
                    --output "$HLS_PROXY_CONFIG" || true
            fi
            if [ ! -f "$HLS_PROXY_CONFIG" ]; then
                echo "WARNING: HLS proxy config not found at $HLS_PROXY_CONFIG skipping HLS proxy"
            else
                echo "Starting HLS Proxy on port $HLS_PROXY_PORT..."
                python3 modules/hls_proxy.py \
                    --config "$HLS_PROXY_CONFIG" \
                    --port "$HLS_PROXY_PORT" \
                    --bind "$HLS_PROXY_BIND" &
                HLS_PID=$!
                _BG_PIDS="$_BG_PIDS $HLS_PID"
                echo "HLS Proxy started (PID $HLS_PID)"
            fi
        fi
    fi

    # Start security monitor if enabled
    if [ "$MONITOR" = "true" ]; then
        if [ ! -f "modules/monitoring.py" ]; then
            echo "ERROR: modules/monitoring.py not found cannot start monitor"
            exit 1
        fi

        # FIX: Build monitor command array with explicit --pid (avoids flaky auto-detection)
        # FIX: Log to persistent logs/ directory instead of /tmp
        MONITOR_CMD=(
            python3 modules/monitoring.py
            --proxy-mode
            --proxy-port "$MONITOR_PORT"
            --target-port "$PORT"
            --log "logs/audit.log"
            --alerts "logs/audit_alerts.log"
        )
        if [ -n "$O11_PID" ] && kill -0 "$O11_PID" 2>/dev/null; then
            MONITOR_CMD+=(--pid "$O11_PID")
        fi
        if [ -n "${MONITOR_ARGS:-}" ]; then
            MONITOR_CMD+=($MONITOR_ARGS)
        fi

        echo "Security monitor enabled"
        echo "  Proxy port:   $MONITOR_PORT  (-> o11 API :$PORT)"
        echo "  Process scan: PID $O11_PID"
        echo "  File watch:   keys.txt, providers/, logs/, hls/"
        echo "  Audit log:    logs/audit.log"
        echo "  Alert log:    logs/audit_alerts.log"
        echo ""
        echo "Starting security monitor on port $MONITOR_PORT..."
        echo "Press Ctrl+C to stop"
        echo ""

        exec "${MONITOR_CMD[@]}"
    else
        # No foreground monitor keep the script alive
        echo ""
        echo "All services running. Press Ctrl+C to stop."
        echo ""
        wait -n 2>/dev/null || wait
    fi

else
    # Direct mode: run o11pro directly (no proxies)
    echo "Press Ctrl+C to stop"
    echo ""
    exec "./$BINARY" $ARGS       # FIX: was "$BINARY" (not in PATH)
fi