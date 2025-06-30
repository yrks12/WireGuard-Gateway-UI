# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Run the application:**
```bash
python run.py
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Testing and linting:**
```bash
pytest                    # Run tests
pytest --cov             # Run tests with coverage
black .                  # Format code
flake8 .                 # Lint code
```

**Database operations:**
All database operations are handled automatically by the Flask app using SQLAlchemy.

## Architecture Overview

This is a **Python Flask web application** for managing WireGuard VPN tunnels with system integration for NAT rules and monitoring.

### Backend Architecture (Flask)
- **Flask app factory pattern**: Main app created in `app/__init__.py` with blueprints
- **SQLAlchemy ORM**: Database models in `app/models/` (User, EmailSettings, AlertHistory, Client)
- **Blueprint-based routing**: Routes split between `app/routes/main.py` (main functionality) and `app/routes/auth.py` (authentication)
- **Service layer pattern**: Business logic in `app/services/` modules for WireGuard, networking, monitoring, etc.

### Key Services Architecture
- **WireGuardService** (`app/services/wireguard.py`): Core WireGuard config validation and operations
- **ConfigStorageService** (`app/services/config_storage.py`): Manages client configs and metadata storage
- **IptablesManager** (`app/services/iptables_manager.py`): Handles NAT/forwarding rules
- **WireGuardMonitor** (`app/services/wireguard_monitor.py`): Connection monitoring and alerting
- **AutoReconnectService** (`app/services/auto_reconnect.py`): Automatic reconnection on DNS changes
- **DNSResolver** (`app/services/dns_resolver.py`): DNS monitoring for DDNS scenarios

### Frontend Architecture
- **Server-rendered Jinja2 templates** in `app/templates/`
- **Bootstrap 5** CSS framework with custom CSS in base template
- **jQuery/JavaScript** for AJAX interactions and dynamic UI updates
- **Responsive design** with mobile-friendly navigation

### System Integration
- **Linux system calls**: Uses `subprocess` to execute `wg-quick`, `iptables`, and other system commands with `sudo`
- **File system operations**: Stores WireGuard configs in instance directory (`./instance/configs/`)
- **Background monitoring**: Task scheduler (`app/tasks.py`) runs connection monitoring

### Security Architecture
- **Flask-Login**: Session-based authentication with mandatory password changes
- **Rate limiting**: Built-in decorator for endpoint protection
- **Sudo integration**: Controlled system command execution for WireGuard operations
- **Input validation**: Strict validation of WireGuard configs and network subnets

### Data Flow
1. **Config Upload**: User uploads .conf → WireGuardService validates → ConfigStorageService stores
2. **Client Activation**: User activates → `wg-quick up` → IptablesManager sets NAT rules
3. **Monitoring**: WireGuardMonitor checks handshakes → EmailService sends alerts → AutoReconnectService handles failures

## Key Patterns Used

- **Factory pattern**: App creation in `create_app()`
- **Service layer**: Business logic separated from routes
- **Decorator pattern**: Rate limiting and authentication decorators
- **Repository pattern**: ConfigStorageService for data persistence
- **Observer pattern**: DNS change callbacks trigger auto-reconnection

## Important Implementation Notes

- **Config validation**: AllowedIPs cannot be `0.0.0.0/0` - forces users to specify actual subnets
- **Pending configs**: Invalid configs with `0.0.0.0/0` are stored temporarily for user correction
- **Sudo requirements**: Most WireGuard operations require sudo privileges
- **Interface naming**: WireGuard interface names derived from config filenames
- **Database migrations**: Uses SQLAlchemy with `db.create_all()` for table creation