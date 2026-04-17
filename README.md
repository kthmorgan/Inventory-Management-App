# Inventory Management App

A lightweight, self-hosted inventory tracking system with a web UI and CLI. Built for home labs, small businesses, or anyone who wants a simple way to track equipment, devices, and supplies.

- **Web UI** — Dark-themed dashboard with search, filter, and photo upload
- **REST API** — Full CRUD API at `/api/items`
- **CLI** — Command-line tool for scripting and quick lookups
- **SQLite** — Zero-config database, single file, easy to back up
- **LAN-friendly** — Runs on your local network, no cloud required

## Quick Start

```bash
# Clone or copy the inventory-dist directory
cd inventory-dist

# Run the installer
./install.sh

# Start the server
python3 app.py
```

Open `http://<your-ip>:8480` in your browser.

## Requirements

- **Python 3.8+**
- **pip** (for installing dependencies)
- Packages installed by `install.sh`:
  - `flask`
  - `requests`

The install script will offer to install Python and pip if they're missing (Debian/Ubuntu, Fedora, RHEL).

## Installation

### Option 1: Manual

```bash
cd inventory-dist
pip3 install flask requests
python3 -c "from app import init_db; init_db()"
python3 app.py
```

### Option 2: Install Script

```bash
cd inventory-dist
./install.sh
```

### Option 3: Systemd Service (auto-start on boot)

After running `install.sh`:

```bash
# Update the service file with your user and install path
sudo sed -i "s|__USER__|$(whoami)|; s|__INSTALLDIR__|$(pwd)|" inventory.service
sudo cp inventory.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inventory
```

Manage it with:

```bash
sudo systemctl status inventory
sudo systemctl restart inventory
sudo systemctl stop inventory
```

## Configuration

The app runs on **port 8480** by default. To change it, edit the last line of `app.py`:

```python
app.run(host='0.0.0.0', port=8480)
```

All data is stored in `inventory.db` (SQLite) in the app directory. Photos are stored in `static/photos/`.

## CLI Reference

The CLI tool (`cli.py`) provides full inventory management from the terminal.

### Add an item

```bash
python3 cli.py add --name "Dell PowerEdge R730" \
  --category "Server" \
  --location "Server Rack" \
  --serial "SVCR730001" \
  --purchase-date "2024-01-15" \
  --value 450.00 \
  --qty 1 \
  --description "2U rack server, 24-core, 128GB RAM" \
  --notes "Running Proxmox"
```

### List items

```bash
# All items
python3 cli.py list

# Filter by category
python3 cli.py list --category "Server"

# Filter by location
python3 cli.py list --location "Server Rack"

# Search within results
python3 cli.py list --search "dell"

# Output formats
python3 cli.py list --format json
python3 cli.py list --format short
```

### Show item details

```bash
python3 cli.py show 5

# JSON format
python3 cli.py show 5 --format json
```

### Update an item

```bash
python3 cli.py update 5 --location "New Rack" --notes "Moved to rack B"
```

### Remove an item

```bash
python3 cli.py remove 5
```

### Search items

```bash
python3 cli.py search dell rack server
```

Full-text search across name, description, notes, location, serial number, and category.

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/items` | List all items (supports `?search=`, `?category=`, `?location=`) |
| GET | `/api/items/<id>` | Get single item |
| POST | `/api/items` | Create item (JSON body or form data with photo) |
| PUT | `/api/items/<id>` | Update item |
| DELETE | `/api/items/<id>` | Delete item |

Example:

```bash
# Create an item
curl -X POST http://localhost:8480/api/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Item", "category": "Electronics"}'

# Search items
curl "http://localhost:8480/api/items?search=dell"

# Get item details
curl http://localhost:8480/api/items/5
```

## Categories

Categories are freeform text fields — no setup needed. Just type a category name when adding items and it becomes a filter option in the web UI.

## Backup

The entire database is a single file (`inventory.db`). To back up:

```bash
cp inventory.db inventory.db.bak.$(date +%Y%m%d)
```

Photos are in `static/photos/` and can be backed up alongside the database.

## File Structure

```
inventory-dist/
├── app.py              # Web application + REST API
├── cli.py              # Command-line interface
├── schema.sql          # Database schema
├── install.sh          # Installation script
├── inventory.service   # Systemd service template
├── README.md           # This file
├── static/
│   ├── style.css       # Dark theme stylesheet
│   └── photos/         # Item photos (uploaded via web UI)
└── templates/
    ├── index.html       # Main listing page
    ├── detail.html      # Item detail page
    └── form.html        # Add/edit item form
```

## License

MIT — use it, modify it, share it.