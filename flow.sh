#!/bin/bash
# Interview Flow - Quick Start (desktop app)
# Requires: Python 3.10+
# On Linux also requires WebKitGTK:
#   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0
# Loads .env automatically when present.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".env" ]; then
    set -a
    # Strip Windows \r so CRLF .env files work under WSL / Linux
    # shellcheck disable=SC1091
    source <(tr -d '\r' < ".env")
    set +a
fi

echo "Interview Flow - AI-Powered Interview Coach"
echo "=================================================="

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'" 2>/dev/null || {
    echo "Python 3.10+ is required"
    exit 1
}

# Set up virtual environment
VENV_DIR=".venv"
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" || {
        echo ""
        echo "ERROR: Could not create virtual environment."
        echo "On Ubuntu/Debian/WSL run: sudo apt install python3-venv python3-pip"
        exit 1
    }
fi

echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt --quiet

# Create data directory
mkdir -p data

echo ""
echo "Launching Interview Flow desktop app..."
echo ""

python3 -m app.desktop
