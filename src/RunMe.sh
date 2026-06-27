#!/usr/bin/env bash
# RunMe.sh – o11pro launcher
#
# Starts the Go binary, HLS proxy, and security monitor.
# Run from inside src/ (setup.sh handles this automatically).
#
# Usage:
#   ./RunMe.sh                    # default port 1337
#   ./RunMe.sh 8080               # custom port
#   ./RunMe.sh 8080 4             # custom port + verbose=4
#   GOMEMLIMIT=4G ./RunMe.sh      # override memory limit
#   MAX_STREAMS=8 ./RunMe.sh      # limit concurrent streams
#   MONITOR=true ./RunMe.sh      # enable security monitor
#   HLS_PROXY=false ./RunMe.sh    # disable HLS proxy

set -euo pipefail

# ─── Config Defaults ───────────────────────────────────────────────────
MONITOR="${MONITOR:-false}"
MONITOR_PORT="${MONITOR_PORT:-1339}"

HLS_PROXY="${HLS_PROXY:-true}"
HLS_PROXY_PORT="${HLS_PROXY_PORT:-1338}"
HLS_PROXY_BIND="${HLS_PROXY_BIND:-0.0.0.0}"

KID_PATCH_OFFSET="${KID_PATCH_OFFSET:-0x15625cd}"

PORT="${1:-1337}"
VERBOSE="${2:-2}"
BIND="${BIND:-0.0.0.0}"

GOMEMLIMIT="${GOMEMLIMIT:-2GiB}"
KEEP_FALSE=true
MAX_STREAMS="${MAX_STREAMS:-0}"
HTTPS="${HTTPS:-false}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin1337}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
HLS_PROXY_CONFIG="${HLS_PROXY_CONFIG:-$SCRIPT_DIR/cache/orig_urls.json}"

export PATH="$VENV_DIR/bin:/usr/bin:/bin:/usr/local/bin:${PATH:-}"
cd "$SCRIPT_DIR"

# ─── Colors ────────────────────────────────────────────────────────────
BLD='\033[1m'; DIM='\033[2m'
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'; CYN='\033[0;36m'
RST='\033[0m'
CHECK="${GRN}\xE2\x9C\x94${RST}"; CROSS="${RED}\xE2\x9C\x98${RST}"
ARROW="${CYN}\xE2\x96\xB6${RST}"

ok()   { echo -e "  ${CHECK} ${BLD}$1${RST} $2"; }
info() { echo -e "  ${ARROW} ${DIM}$1${RST}"; }
warn() { echo -e "  ${YLW}\xE2\x9A\xA0${RST} ${BLD}$1${RST} $2"; }
fail() { echo -e "  ${CROSS} ${RED}$1${RST}"; exit 1; }

# ─── Pre-flight ────────────────────────────────────────────────────────
BINARY="o11pro"

KID_PATCH=$(python3 -c "
with open('$BINARY','rb') as f:
    f.seek($KID_PATCH_OFFSET)
    b = f.read(4)
    print('OK' if b == b'%02x' else 'MISSING')
" 2>/dev/null || echo "CHECK_FAILED")
[ "$KID_PATCH" = "OK" ] || warn "KID patch" "NOT detected"

if [ ! -f "keys.txt" ]; then
  touch keys.txt
fi
cp keys.txt keys/ 2>/dev/null || true

mkdir -p hls/live keys epg dl manifests offair overlay logos fonts \
         rec scripts logs providers cache

# ─── Build Args ────────────────────────────────────────────────────────
ARGS="-c o11.cfg -p $PORT -b $BIND -stdout -v $VERBOSE -providers providers -usecdm"

if [ "$KEEP_FALSE" = "true" ]; then
  ARGS="$ARGS -keep=false"
fi

if [ "$HTTPS" = "true" ]; then
  ARGS="$ARGS -https"
  [ -f "server.crt" ] && [ -f "server.key" ] || warn "HTTPS" "missing certs"
fi

if [ -n "$ADMIN_USER" ] && [ -n "$ADMIN_PASS" ]; then
  ARGS="$ARGS -user $ADMIN_USER -password $ADMIN_PASS"
fi

GOMEMLIMIT_BYTES=0
if [ -n "$GOMEMLIMIT" ] && [ "$GOMEMLIMIT" != "0" ]; then
  GOMEMLIMIT_BYTES=$(python3 -c "
import re
s = '$GOMEMLIMIT'.strip()
m = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]i?B?|B)?\$', s, re.I)
if not m: print(0); exit()
n = float(m.group(1))
unit = (m.group(2) or 'B').upper()
mult = {'B':1, 'KB':1000, 'KIB':1024, 'MB':1000000, 'MIB':1048576,
        'GB':1000000000, 'GIB':1073741824, 'TB':1000000000000, 'TIB':1099511627776}
print(int(n * mult.get(unit, 1)))
" 2>/dev/null || echo "0")
fi

[ "$GOMEMLIMIT_BYTES" -gt 0 ] && export GOMEMLIMIT="$GOMEMLIMIT_BYTES"
export GOTRACEBACK="${GOTRACEBACK:-0}"

# ─── Launch ────────────────────────────────────────────────────────────

# Kill existing instance on our port
EXISTING_PID=$(pgrep -f "o11pro.*-p $PORT" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
  info "Killing existing o11pro on :${PORT} (PID ${EXISTING_PID})..."
  kill "$EXISTING_PID" 2>/dev/null || true
  sleep 2
  if kill -0 "$EXISTING_PID" 2>/dev/null; then
    kill -9 "$EXISTING_PID" 2>/dev/null || true
    sleep 1
  fi
fi

if [ "$MONITOR" != "true" ] && [ "$HLS_PROXY" != "true" ]; then
  echo -e "  ${GRN}\xE2\x96\xB6${RST}  ${BLD}o11pro${RST} on :${PORT}"
  exec "./$BINARY" $ARGS
fi

# ── Background mode ─────────────────────────────────────────────────
_BG_PIDS=""

cleanup_all() {
  echo
  echo -e "  ${YLW}\xE2\x96\xA0${RST}  ${BLD}Shutting down${RST}..."
  for pid in $_BG_PIDS; do kill "$pid" 2>/dev/null || true; done
  for pid in $_BG_PIDS; do wait "$pid" 2>/dev/null || true; done
  ok "done" ""
}
trap cleanup_all EXIT INT TERM

echo -e "  ${GRN}\xE2\x96\xB6${RST}  ${BLD}Starting o11pro${RST} on :${PORT}..."
"./$BINARY" $ARGS &
O11_PID=$!
_BG_PIDS="$O11_PID"

info "Waiting for port ${PORT}..."
_O11_TRIES=0
while [ $_O11_TRIES -lt 30 ]; do
  _O11_TRIES=$((_O11_TRIES + 1))
  if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',$PORT)); s.close()" 2>/dev/null; then
    ok "ready" ":${PORT}"
    break
  fi
  [ $_O11_TRIES -eq 30 ] && fail "o11pro did not start within 30s"
  sleep 1
done

# HLS Proxy
if [ "$HLS_PROXY" = "true" ]; then
  if [ ! -f "modules/hls_proxy.py" ]; then
    warn "HLS proxy" "not found — skipping"
  else
    if [ -f "modules/generate_orig_urls.py" ]; then
      python3 modules/generate_orig_urls.py \
        --dir "$SCRIPT_DIR/providers" \
        --output "$HLS_PROXY_CONFIG" 2>/dev/null || true
    fi

    if [ ! -f "$HLS_PROXY_CONFIG" ]; then
      warn "HLS proxy" "config missing — skipping"
    else
      echo -e "  ${GRN}\xE2\x96\xB6${RST}  ${BLD}HLS proxy${RST} on :${HLS_PROXY_PORT}..."
      python3 modules/hls_proxy.py \
        --config "$HLS_PROXY_CONFIG" \
        --port "$HLS_PROXY_PORT" \
        --bind "$HLS_PROXY_BIND" &
      _BG_PIDS="$_BG_PIDS $!"
      ok "HLS proxy" "PID $!"
    fi
  fi
fi

# Security monitor
if [ "$MONITOR" = "true" ]; then
  [ -f "modules/monitoring.py" ] || fail "monitoring.py not found"

  MONITOR_CMD=(
    python3 modules/monitoring.py
    --proxy-mode
    --proxy-port "$MONITOR_PORT"
    --target-port "$PORT"
    --log "logs/audit.log"
    --alerts "logs/audit_alerts.log"
  )
  if [ "$HLS_PROXY" = "true" ]; then
    MONITOR_CMD+=(--hls-target "127.0.0.1:$HLS_PROXY_PORT")
  fi
  if [ -n "$O11_PID" ] && kill -0 "$O11_PID" 2>/dev/null; then
    MONITOR_CMD+=(--pid "$O11_PID")
  fi
  [ -n "${MONITOR_ARGS:-}" ] && MONITOR_CMD+=($MONITOR_ARGS)

  echo -e "  ${GRN}\xE2\x96\xB6${RST}  ${BLD}Security monitor${RST} on :${MONITOR_PORT}"
  "${MONITOR_CMD[@]}" &
  _BG_PIDS="$_BG_PIDS $!"
  ok "monitor" "PID $!"

  echo
  echo -e "  ${DIM}  Web UI     http://${BIND}:${PORT}${RST}"
  echo -e "  ${DIM}  HLS proxy  http://${BIND}:${HLS_PROXY_PORT}/channel/{name}/master.m3u8${RST}"
  echo -e "  ${DIM}  Monitor    http://${BIND}:${MONITOR_PORT} (optional, with HTTP inspection)${RST}"
  echo -e "  ${DIM}  Audit log  logs/audit.log${RST}"
fi

echo
echo -e "  ${DIM}All services running. Press Ctrl+C to stop.${RST}"
echo
wait -n 2>/dev/null || wait