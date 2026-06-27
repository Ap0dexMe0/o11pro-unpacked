#!/bin/sh
# install.sh – One-command installer for o11pro-unpacked
#
# Usage:
#   sh -c "$(curl -fsSL https://raw.githubusercontent.com/Ap0dexMe0/o11pro-unpacked/main/install.sh)"
#   sh -c "$(wget -O-  https://raw.githubusercontent.com/Ap0dexMe0/o11pro-unpacked/main/install.sh)"
#   sh -c "$(fetch -o - https://raw.githubusercontent.com/Ap0dexMe0/o11pro-unpacked/main/install.sh)"
#
# Environment:
#   O11PRO_DIR    Install directory (default: /root/o11pro-unpacked, root required)
#   O11PRO_PORT   Server port (default: 1337)
#   O11PRO_VERBOSE Log level 0-5 (default: 2)
#   O11PRO_USER   Admin username
#   O11PRO_PASS   Admin password
#   O11PRO_YES    Skip confirmation prompts (set to 1)
#   O11PRO_BRANCH Git branch to clone (default: main)
#
# Options:
#   --yes, -y     Non-interactive mode (auto-confirm all prompts)
#   --help, -h    Show this help message

set -eu

REPO_URL="https://github.com/Ap0dexMe0/o11pro-unpacked.git"
REPO_RAW="https://raw.githubusercontent.com/Ap0dexMe0/o11pro-unpacked"
BRANCH="${O11PRO_BRANCH:-main}"

# ─── Parse flags ─────────────────────────────────────────────────────────
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) FORCE=1 ;;
    --help|-h)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
  esac
done
[ "${O11PRO_YES:-0}" = "1" ] && FORCE=1

# ─── Symbols ─────────────────────────────────────────────────────────────
# Use Unicode symbols in bash/zsh, ASCII fallback in POSIX sh (dash).
_ok='*'; _info='>'; _warn='!'; _fail='x'
_test=$(printf '\xE2\x9C\x94' 2>/dev/null) || true
case "$_test" in *\\*) ;; *)
  _ok='\xE2\x9C\x94'; _info='\xE2\x96\xB6'; _warn='\xE2\x9A\xA0'; _fail='\xE2\x9C\x98'
esac

ok()    { printf "  ${_ok} %s %s\n" "$1" "${2-}"; }
info()  { printf "  ${_info} %s\n" "$1"; }
warn()  { printf "  ${_warn} %s %s\n" "$1" "${2-}"; }
fail()  { printf "  ${_fail} %s\n" "$1"; exit 1; }
sep()   { printf "  ----------------------------------------\n"; }
header(){ printf "\n%s\n%s\n\n" "$1" "${2-}"; }

# ─── Check prerequisites ─────────────────────────────────────────────────
header "o11pro Installer" "One-command setup for o11pro-unpacked"

has_cmd() { command -v "$1" >/dev/null 2>&1; }

info "Checking prerequisites..."

if ! has_cmd git; then
  fail "git is required but not installed.\n       Install it with your package manager (apt install git, yum install git, etc.)"
fi
ok "git" "$(git --version 2>/dev/null)"

if ! has_cmd python3; then
  fail "python3 is required but not installed."
fi
ok "python3" "$(python3 --version 2>/dev/null)"

FETCH_CMD=""
DOWNLOAD_CMD=""
DOWNLOAD_PIPE=""
if has_cmd curl; then
  FETCH_CMD="curl -fsSL"
  DOWNLOAD_CMD="curl -fsSL -o"
  DOWNLOAD_PIPE="curl -fsSL"
  ok "curl" "available"
elif has_cmd wget; then
  FETCH_CMD="wget -O-"
  DOWNLOAD_CMD="wget -O"
  DOWNLOAD_PIPE="wget -O-"
  ok "wget" "available"
elif has_cmd fetch; then
  FETCH_CMD="fetch -o -"
  DOWNLOAD_CMD="fetch -o"
  DOWNLOAD_PIPE="fetch -o -"
  ok "fetch" "available"
else
  fail "curl, wget, or fetch is required to download files."
fi

# ─── Determine install directory ─────────────────────────────────────────
INSTALL_DIR="${O11PRO_DIR:-/root/o11pro-unpacked}"

# ─── Root check ──────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
  fail "This installer must be run as root.\n       Install directory ${INSTALL_DIR} requires root privileges.\n       Try: sudo sh -c \"\$(curl ...)\""
fi
ok "root" "privileges confirmed"

if [ "$FORCE" = "0" ] && [ -d "$INSTALL_DIR" ]; then
  printf "  Directory %s already exists.\n" "$INSTALL_DIR"
  printf "  Overwrite? [y/N] "; read -r REPLY
  case "$REPLY" in
    [yY]|[yY][eE][sS]) ;;
    *) fail "Installation cancelled." ;;
  esac
fi

# ─── Install ─────────────────────────────────────────────────────────────
sep

info "Installing to $INSTALL_DIR..."

# Ensure parent directory exists
PARENT_DIR=$(dirname "$INSTALL_DIR")
mkdir -p "$PARENT_DIR"

# Clone or update the repository
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating existing installation..."
  cd "$INSTALL_DIR"
  git pull --ff-only origin "$BRANCH" 2>/dev/null || {
    warn "git pull failed, re-cloning..."
    cd /
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  }
else
  rm -rf "$INSTALL_DIR"
  git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi
ok "repository" "cloned to $INSTALL_DIR"

cd "$INSTALL_DIR"

# ─── Python virtual environment ──────────────────────────────────────────
VENV_DIR="$INSTALL_DIR/src/venv"
if [ ! -d "$VENV_DIR" ]; then
  info "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi
ok "venv" "ready"

# ─── Install Python dependencies ─────────────────────────────────────────
if [ -f "requirements.txt" ]; then
  info "Installing Python dependencies..."
  "$VENV_DIR/bin/pip" install --upgrade pip -q 2>/dev/null || true
  "$VENV_DIR/bin/pip" install -r requirements.txt -q 2>/dev/null || warn "Some pip packages failed to install"
  ok "dependencies" "installed"
fi

# ─── Make binary executable ──────────────────────────────────────────────
BINARY=""
for b in src/o11pro src/o11; do
  [ -f "$b" ] && BINARY="$b" && break
done

if [ -n "$BINARY" ]; then
  chmod +x "$BINARY"
  ok "binary" "ready ($BINARY)"
else
  warn "binary" "not found in src/ — check your download"
fi

# Make launcher executable
[ -f "src/RunMe.sh" ] && chmod +x "src/RunMe.sh"
ok "launcher" "ready"

# ─── FFmpeg ──────────────────────────────────────────────────────────────
if has_cmd ffmpeg; then
  ok "ffmpeg" "$(ffmpeg -version 2>&1 | head -1 | sed 's/ffmpeg version //' | sed 's/ Copyright.*//')"
else
  info "ffmpeg not found — installing..."
  if has_cmd apt-get; then
    apt-get update -qq && apt-get install -y -qq ffmpeg
  elif has_cmd yum; then
    yum install -y ffmpeg 2>/dev/null || \
    yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm 2>/dev/null && \
    yum install -y ffmpeg ffmpeg-devel
  elif has_cmd apk; then
    apk add ffmpeg
  elif has_cmd zypper; then
    zypper install -y ffmpeg
  elif has_cmd pacman; then
    pacman -S --noconfirm ffmpeg
  else
    warn "ffmpeg" "could not install automatically — install manually"
  fi
  if has_cmd ffmpeg; then
    ok "ffmpeg" "$(ffmpeg -version 2>&1 | head -1 | sed 's/ffmpeg version //' | sed 's/ Copyright.*//')"
  fi
fi

# ─── Create runtime directories ──────────────────────────────────────────
mkdir -p "$INSTALL_DIR/src/hls/live"
mkdir -p "$INSTALL_DIR/src/keys"
mkdir -p "$INSTALL_DIR/src/epg"
mkdir -p "$INSTALL_DIR/src/dl"
mkdir -p "$INSTALL_DIR/src/manifests"
mkdir -p "$INSTALL_DIR/src/offair"
mkdir -p "$INSTALL_DIR/src/overlay"
mkdir -p "$INSTALL_DIR/src/logos"
mkdir -p "$INSTALL_DIR/src/fonts"
mkdir -p "$INSTALL_DIR/src/rec"
mkdir -p "$INSTALL_DIR/src/scripts"
mkdir -p "$INSTALL_DIR/src/logs"
mkdir -p "$INSTALL_DIR/src/providers"
mkdir -p "$INSTALL_DIR/src/cache"
ok "directories" "created"

# ─── Done — launch ───────────────────────────────────────────────────────
sep
echo
printf "  ${_ok} o11pro installed successfully\n"
echo
printf "  Starting o11pro...\n"
echo

# Verify that the launcher exists and is executable
if [ ! -f "$INSTALL_DIR/src/RunMe.sh" ]; then
  fail "RunMe.sh not found in src/ — cannot start."
fi
if [ ! -x "$INSTALL_DIR/src/RunMe.sh" ]; then
  chmod +x "$INSTALL_DIR/src/RunMe.sh"
fi

cd "$INSTALL_DIR/src"
exec ./RunMe.sh