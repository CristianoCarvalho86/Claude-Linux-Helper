#!/usr/bin/env bash
# setup.sh – Install Claude-Linux-Helper on Ubuntu / Debian
# Usage: bash setup.sh

set -euo pipefail

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 1. Check OS ────────────────────────────────────────────────────────────────
if ! command -v apt &>/dev/null; then
    warn "apt not found – this script is designed for Ubuntu/Debian."
    warn "You can still install manually: pip3 install -r requirements.txt"
fi

# ── 2. System packages ─────────────────────────────────────────────────────────
info "Updating package lists…"
sudo apt-get update -qq

info "Installing Python3 and pip…"
sudo apt-get install -y python3 python3-pip python3-venv -qq

# ── 3. Virtual environment ─────────────────────────────────────────────────────
VENV_DIR="$(pwd)/venv"

if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment at $VENV_DIR…"
    python3 -m venv "$VENV_DIR"
else
    info "Virtual environment already exists at $VENV_DIR."
fi

info "Activating virtual environment and installing dependencies…"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 4. API key reminder ────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  ACTION REQUIRED: Set your Anthropic API key     ${NC}"
echo -e "${YELLOW}══════════════════════════════════════════════════${NC}"
echo ""
echo "  1. Get a free API key at: https://console.anthropic.com/"
echo ""
echo "  2. Export it for the current session:"
echo "       export ANTHROPIC_API_KEY='sk-ant-...'"
echo ""
echo "  3. To make it permanent, add it to ~/.bashrc:"
echo "       echo \"export ANTHROPIC_API_KEY='sk-ant-...'\" >> ~/.bashrc"
echo "       source ~/.bashrc"
echo ""

# ── 5. Run instructions ────────────────────────────────────────────────────────
info "Setup complete! To start Claude-Linux-Helper:"
echo ""
echo "    source venv/bin/activate"
echo "    python3 main.py"
echo ""
