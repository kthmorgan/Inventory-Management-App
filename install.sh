#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Inventory Management App Installer ===${NC}"
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}Python 3 not found. Installing...${NC}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y python3 python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3 python3-pip
    else
        echo "Please install Python 3 manually and re-run this script."
        exit 1
    fi
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VER"

# Install dependencies - try multiple methods
echo ""
echo "Installing Python dependencies (flask, requests)..."

install_deps() {
    # Method 1: pip3
    if command -v pip3 &>/dev/null; then
        pip3 install flask requests && return 0
    fi
    # Method 2: pip
    if command -v pip &>/dev/null; then
        pip install flask requests && return 0
    fi
    # Method 3: python3 -m pip (works even without pip in PATH)
    if python3 -m pip install flask requests 2>/dev/null; then
        return 0
    fi
    # Method 4: sudo python3 -m pip (system-wide if user install fails)
    if sudo python3 -m pip install flask requests; then
        return 0
    fi
    # Method 5: apt (Debian/Ubuntu)
    if command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y python3-flask python3-requests && return 0
    fi
    return 1
}

if install_deps; then
    echo "Dependencies installed."
else
    echo -e "${YELLOW}Warning: Could not install dependencies automatically.${NC}"
    echo "Please install them manually:"
    echo "  pip3 install flask requests"
    echo ""
    echo "Or on Debian/Ubuntu:"
    echo "  sudo apt install python3-flask python3-requests"
    exit 1
fi

# Create database
echo ""
echo "Initializing database..."
python3 -c "from app import init_db; init_db()"

# Create photo directory
mkdir -p static/photos

# Determine install directory for service file
INSTALL_DIR="$(cd "$SCRIPT_DIR" && pwd)"
CURRENT_USER="$(whoami)"

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Quick start:"
echo "  python3 app.py"
echo ""
echo "The web UI will be available at http://<your-ip>:8480"
echo ""
echo "To install as a systemd service (auto-starts on boot):"
echo "  sudo sed -i \"s|__USER__|$CURRENT_USER|; s|__INSTALLDIR__|$INSTALL_DIR|\" inventory.service"
echo "  sudo cp inventory.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now inventory"
echo ""
echo "CLI usage:"
echo "  python3 cli.py add --name \"Item Name\" --category Electronics --location Desk"
echo "  python3 cli.py list"
echo "  python3 cli.py search <query>"
echo "  python3 cli.py --help"