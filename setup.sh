#!/usr/bin/env bash
# setup.sh – Fully automatic environment setup + launcher
#
# Fixed for src/ layout: binary, configs, and RunMe.sh live under src/
# This script creates the venv at the project root and delegates to src/RunMe.sh
#
# Usage:
#   ./setup.sh                        # o11pro + hls_proxy (default)
#   MONITOR=true ./setup.sh           # o11pro + hls_proxy + security monitor
#   HLS_PROXY=false ./setup.sh        # o11pro only
#   MONITOR=true HLS_PROXY=false ./setup.sh  # o11pro + security monitor only
#   ./setup.sh 8080                   # custom port
#   ./setup.sh 8080 4                 # custom port + verbose=4
#
# Environment variables (pass before or alongside):
#   MONITOR=true          Enable security monitoring proxy (port 19998)
#   MONITOR_PORT=19998    Monitor proxy port
#   HLS_PROXY=true        Enable HLS rewrite proxy (port 9999)
#   HLS_PROXY_PORT=9999   HLS proxy port
#   GOMEMLIMIT=4G         Override Go memory limit
#   MAX_STREAMS=8         Limit concurrent streams
#   ADMIN_USER=admin      Static admin username
#   ADMIN_PASS=secret     Static admin password

set -euo pipefail

SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SETUP_DIR/src"

echo "=========================================="
echo "  Automatic setup and launch"
echo "  Project root: $SETUP_DIR"
echo "  Source dir:   $SRC_DIR"
echo "=========================================="

if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Installing..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-pip
    else
        echo "ERROR: No supported package manager. Please install Python 3 manually."
        exit 1
    fi
else
    echo "Python 3 is installed: $(python3 --version)"
fi

VENV_DIR="$SETUP_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

echo "Installing / updating requirements from requirements.txt ..."
"$VENV_DIR/bin/pip" install --upgrade pip -q 2>&1 | tail -1
if [ -f "$SETUP_DIR/requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r "$SETUP_DIR/requirements.txt" -q 2>&1 | tail -3
    echo "Dependencies installed."
else
    echo "Warning: requirements.txt not found – skipping package installation."
fi

RUNME="$SRC_DIR/RunMe.sh"
if [ -f "$RUNME" ]; then
    # Make it executable
    chmod +x "$RUNME"

    # Check if we already patched it (look for our marker)
    if ! grep -q "# VENV_PATCHED" "$RUNME"; then
        echo "Patching RunMe.sh to use virtual environment..."
        # Insert venv PATH right after the existing export PATH line
        sed -i.bak \
            -e 's|^export PATH="/usr/bin:/bin:/usr/local/bin:${PATH:-}"|# VENV_PATCHED\nexport PATH="'"$VENV_DIR"'/bin:/usr/bin:/bin:/usr/local/bin:${PATH:-}"|' \
            "$RUNME"
        echo "RunMe.sh patched (backup saved as RunMe.sh.bak)"
    else
        echo "RunMe.sh already patched."
    fi
else
    echo "ERROR: RunMe.sh not found at $RUNME"
    exit 1
fi

echo "Checking required files in $SRC_DIR ..."
REQUIRED_FILES=("o11pro" "o11.cfg" "providers/sample.cfg")
MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SRC_DIR/$f" ]; then
        echo "ERROR: Required file 'src/$f' not found."
        MISSING=1
    fi
done
if [ $MISSING -eq 1 ]; then
    echo "Please place all required files under src/."
    exit 1
fi
echo "All required files present."

echo "Building hls_proxy channel URL config ..."
"$VENV_DIR/bin/python3" -c "
import json, sys
cfg_path = '$SRC_DIR/providers/sample.cfg'
out_path = '/tmp/o11pro_orig_urls.json'
try:
    d = json.load(open(cfg_path))
    urls = {}
    for s in d.get('Streams', []):
        name = s.get('Name', '')
        manifest = s.get('Manifest', '')
        if name and manifest:
            urls[name] = manifest
    if urls:
        json.dump(urls, open(out_path, 'w'), indent=2, ensure_ascii=False)
        print(f'  Wrote {len(urls)} channel URLs to {out_path}')
    else:
        print('  WARNING: No channel URLs found in provider config')
        json.dump({}, open(out_path, 'w'))
except Exception as e:
    print(f'  WARNING: Could not build URL config: {e}')
    json.dump({}, open(out_path, 'w'))
"

echo ""
MODE_PARTS=("o11pro :${1:-19999}")    # FIX: was $1 (unbound when no args)
if [ "${HLS_PROXY:-true}" = "true" ]; then
    MODE_PARTS+=("hls_proxy :${HLS_PROXY_PORT:-9999}")
fi
if [ "${MONITOR:-false}" = "true" ]; then
    MODE_PARTS+=("monitoring :${MONITOR_PORT:-19998}")
fi
echo "Launch mode: ${MODE_PARTS[*]}"

echo ""
echo "=========================================="
echo "  Launching RunMe.sh with venv Python"
echo "=========================================="
# cd into src/ so RunMe.sh finds its binary and configs
cd "$SRC_DIR"
exec ./RunMe.sh "$@"