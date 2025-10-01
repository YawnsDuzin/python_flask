# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ITLog Device Manager** - Industrial IoT sensor monitoring platform built with Flask for Raspberry Pi edge computing environments. Provides real-time sensor data streaming, device management, and system administration through a responsive web interface.

## Development Commands

### Running the Application
```bash
# Standard execution
python app.py

# The server starts on http://0.0.0.0:5000 (configurable via database config)
```

### Virtual Environment Setup
```bash
# Create virtual environment
python -m venv venv_webapp

# Activate (Windows)
venv_webapp\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Building Windows Executable
```bash
# Use the provided build script
build_exe.bat

# Output will be in release/ folder with all required files
```

### Testing
```bash
# Simulate sensor data for testing
python Extend/SocketServer_SensorTest.py

# Test sensor dashboard API
python test_sensor_dashboard_api.py

# With custom server and key
python test_sensor_dashboard_api.py http://192.168.1.100:5000 your-api-key
```

## Core Architecture

### Execution Modes (EXE_MODE in .env)

**SERVER Mode** (Full functionality):
- TCP socket connection to sensor server (port 3000)
- Real-time SSE data streaming
- All management features enabled
- Full API access

**CLIENT Mode** (Limited monitoring):
- No TCP socket connection
- SSE APIs disabled (/api/sensor-stream, /api/public-sensor-stream)
- Auto-login as viewer
- Redirects to sensor dashboard
- Read-only access

### Key Components

**Main Application** (`app.py`):
- Flask server initialization
- TCP client thread for sensor data (SERVER mode only)
- SSE broadcasting to web clients
- Blueprint registration
- Global configuration loading

**Configuration System** (Multi-tier):
1. `.env` file - Database path, execution mode
2. Database `config` table - Primary settings storage
3. `config_sensor.json` - Sensor UI definitions

**User & Security** (`user_manager.py`):
- Three-tier permissions: admin, operator, viewer
- Bcrypt password hashing
- Session management
- Automatic table migration

**Config Manager** (`config_manager.py`):
- Database configuration loading
- Mode-specific settings (gb field)
- JSON structure for nested configs
- Thread-safe caching (5 seconds)

**System Monitor** (`system_monitor.py`):
- Real-time CPU, memory, disk monitoring
- Process information
- Network interfaces status

**Blueprints** (`blueprints/`):
- `api.py` - REST endpoints, SSE streams
- `auth.py` - Login/logout
- `device.py` - Device, CS, LED, Setting CRUD operations
- `sensor.py` - Sensor dashboard, data queries
- `sensor_dashboard.py` - Sensor dashboard API endpoints (CS/font tables)
- `system.py` - Raspberry Pi management
- `client.py` - CLIENT mode features, font_set management
- `user_admin.py` - User management
- `config_admin.py` - Config editor

### Database Schema

**Core Tables**:
- `device` - Sensor devices (idx, name, type, mode, use, port, delay, save_sec)
- `cs` - Communication settings (idx, name, type, use, device, mode, dv_no, com_mode)
- `setting/setting2` - System settings
- `led` - LED display config (idx, type, use, mode, port, display_sec)
- `font_set` - Font configuration (fcode, fname, ftext, fsize, ffont, fstyle, fcolor, fbg)
- `users` - User accounts (id, username, password_hash, permission, created_at)
- `config` - Key-value configuration (id, category, key, value, data_type, gb field for mode filtering)
- `client` - Client devices (idx, name, type, use, ip, port, monitor)

**Sensor Data Tables**:
- `data_pm`, `data_o2`, `data_mq`, `data_nox`, `data_gasm`
- `data_wind`, `data_vibro`, `data_crack`, `data_tilt`, `data_sound`

### Real-time Data Flow

1. **Sensor Server** → TCP Socket (port 3000)
2. **TCP Client Thread** → Parse data → Store in `latest_sensor_data`
3. **SSE Broadcast** → All connected web clients
4. **Web UI** → Dynamic sensor card updates

Data format: `device_id|sensor_type|location|data...^ip_address`

## Critical Implementation Details

### TCP Socket Management
```python
# Only runs in SERVER mode
if EXE_MODE == 'SERVER':
    TCP_HOST = config.get('socketserver', {}).get('TCP_HOST', '127.0.0.1')
    TCP_PORT = config.get('socketserver', {}).get('TCP_PORT', 3000)
```

### SSE API Protection
```python
# Disabled in CLIENT mode
if EXE_MODE == 'CLIENT':
    return Response('This API is disabled in CLIENT mode', status=403)
```

### Config Table gb Field
The `config` table includes a `gb` column for mode-specific settings:
- `DEFAULT` - Shows in all modes
- `SERVER` - Shows only in SERVER mode
- `CLIENT` - Shows only in CLIENT mode

### Sensor Configuration
`config_sensor.json` defines 10 sensor types with:
- Display fields and units
- Badge/status indicators
- Color schemes
- Icon assignments

### API Authentication
Public APIs use key authentication:
```python
# Check sensor_stream_key_server in config table
configured_keys = config.get('api', {}).get('sensor_stream_key_server', ['default-key'])
```

### UI Styling Patterns

**Active/Inactive Row Styling**:
Lists that show "사용유무" (use status) = "Y" are styled with:
- Light mode: Light red background (#fee2e2) with red border
- Dark mode: Gray background (#3f3f46) with red border
- Active badge: Red background with white text
- Applied to: device_list, cs_list, led_list, client_list

**Permission Decorators**:
- `@login_required` - Any authenticated user
- `@operator_required` - Operator or admin only
- `@admin_required` - Admin only

## Common Development Tasks

### Database Operations
```python
# Access database from any blueprint
from app import get_db_connection

conn = get_db_connection()
cursor = conn.execute("SELECT * FROM device WHERE use = 'Y'")
devices = cursor.fetchall()
conn.close()
```

### Adding a New Sensor Type
1. Add definition to `config_sensor.json`
2. Create `data_[type]` table in database
3. Update sensor data parsing in `sensor_dashboard.html`
4. Add to SENSOR_TABLE_MAPPING in `blueprints/sensor.py`

### Modifying Configuration
1. Web UI: `/admin/config/list`
2. Database: Direct edit of `config` table
3. Set appropriate `gb` value for mode-specific settings

### Creating New Blueprint
1. Create file in `blueprints/`
2. Register in `blueprints/__init__.py`
3. Apply permission decorators as needed

### Working with Composite Keys
Some tables use composite primary keys (e.g., font_set with fcode+fname):
```python
# Delete with composite key
conn.execute('DELETE FROM font_set WHERE fcode = ? AND fname = ?', (fcode, fname))
```

## Deployment Notes

### File Structure Requirements
```
release/
├── ITLOG_Device_Manager.exe
├── templates/
├── static/
├── config_sensor.json
├── .env
└── sensor.db (auto-created if missing)
```

### Environment Variables (.env)
```ini
DATABASE_PATH=./
DATABASE_DB=sensor.db
EXE_MODE=SERVER  # or CLIENT
```

### Port Configuration
- Web server: 5000 (default, configurable)
- TCP sensor server: 3000 (configurable)

### Troubleshooting Quick Fixes

**No sensor data appearing**:
- Check EXE_MODE=SERVER in .env
- Verify TCP server at configured host:port
- Check firewall for port 3000

**API returns 403 Forbidden**:
- CLIENT mode disables SSE APIs
- Switch to SERVER mode if needed

**Config changes not appearing**:
- Check gb field matches current EXE_MODE
- Refresh cache with ?refresh=true parameter

**Template not found errors**:
- Ensure templates/ folder is in same directory as executable
- Check template paths use forward slashes

## Migration Notes

### SQL.js to API Migration
The sensor dashboard has migrated from browser-based SQL.js to server-side API endpoints (see MIGRATION_SQL_TO_API.md):
- CS and font table data now served via `/api/sensor-dashboard/` endpoints
- API key authentication required for public access
- Improved security and performance

## Security Considerations

- Change default Flask secret key (app.py line 65)
- Update hardcoded credentials if present
- Configure API keys in database config table
- Set appropriate file permissions on sensor.db
- Enable HTTPS for production deployment

## Performance Considerations

- SSE clients limited by browser connections (~6 per domain)
- Sensor data cached for 5 seconds
- Database writes batched where possible
- TCP reconnection: 5-second retry interval
- Heartbeat: 30-second intervals for SSE

## Dependencies

**Core Requirements** (requirements.txt):
- flask>=2.0.0 - Web framework
- python-dotenv>=0.19.0 - Environment management
- psutil>=5.9.0 - System monitoring
- PyQt5>=5.15.0 - GUI for test tools
- pyinstaller>=5.0.0 - Executable building
- bcrypt>=4.0.0 - Password hashing