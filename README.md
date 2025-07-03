# WireGuard Gateway Web Application

A comprehensive, enterprise-level web application for managing WireGuard VPN tunnels, featuring automated monitoring, alerting, backup systems, and advanced network management capabilities.

**Developed by [YairTech](https://www.yairtech.co.uk)** - Specialists in business automation, custom CRM development, AI integration, and dashboards.

## Features Overview

### 🔒 **Core VPN Management**
- Upload and validate WireGuard client configurations
- Activate/deactivate VPN tunnels with automatic NAT/forwarding rules
- Advanced config validation (prevents `0.0.0.0/0` AllowedIPs)
- Pending configuration management for invalid configs requiring user correction
- Client name preservation and subnet correction workflows

### 📊 **Real-time Monitoring & Alerting**
- **WireGuard Connection Monitor**: Real-time handshake monitoring with 30-minute disconnect threshold
- **Email Alert System**: SMTP-based alerts for disconnected clients with configurable settings
- **Alert History**: Database-backed alert tracking with success/failure status
- **Alert Cooldown**: Anti-spam protection with 1-hour cooldown between alerts
- **Live Dashboard**: Real-time updates of client status and system metrics

### 🌐 **DDNS Monitoring & Auto-Reconnect**
- **Dynamic DNS Monitoring**: Automatic detection of IP address changes for DDNS hostnames
- **Auto-Reconnect Service**: Automatic client reconnection when DNS changes detected
- **Smart Reconnection**: Maximum 3 attempts with 5-minute cooldown periods
- **DNS Change History**: Tracking of hostname IP changes with timestamps
- **Manual Controls**: UI buttons for manual reconnection attempts

### 💾 **Comprehensive Backup & Restore System**
- **Full System Backup**: Complete backup of configurations, databases, and settings
- **Multi-Database Support**: Backs up `app.db`, `configs.db`, and `wireguard.db`
- **Backup Download**: Direct download of backup files with rate limiting
- **Complete Restore**: Full system restore from backup files with validation
- **Automatic Cleanup**: Removal of old backup files after 7 days
- **Integrity Checking**: Backup validation before restore operations

### 🔧 **Advanced Network Management**
- **Router Integration**: Automatic generation of router commands for multiple router types
- **Network Testing**: Per-client connectivity testing with detailed results
- **IPTables Automation**: Dynamic NAT/forwarding rule management
- **IP Forwarding Control**: Live monitoring and control of IP forwarding
- **LAN Interface Detection**: Automatic detection and configuration

### 👥 **User Management System**
- **Multi-User Support**: Complete user management with role-based access
- **Secure Authentication**: Password hashing with forced password change on first login
- **User Administration**: Admin interface for creating and managing users
- **Session Management**: Secure session handling with rate limiting
- **Password Policies**: Enforced password requirements and change workflows

### 🚀 **System Administration**
- **Remote System Control**: Secure server reboot functionality
- **System Metrics**: Real-time CPU, memory, and system load monitoring
- **Monitoring Logs**: Dedicated interface for viewing monitoring events
- **System Cleanup**: Automated cleanup of duplicate entries and orphaned data
- **Status Polling**: Background services for continuous system monitoring

### 🔌 **API & Integration**
- **RESTful API**: Comprehensive API for programmatic access
- **Client Management API**: CRUD operations for all client operations
- **Monitoring API**: Real-time monitoring data and metrics
- **System Control API**: System status and administrative controls
- **Rate Limited Endpoints**: Built-in protection for sensitive operations

## Tech Stack

- **Backend**: Python 3.8+ (Flask) with Jinja2 templates
- **Frontend**: HTML5, CSS3, JavaScript with Bootstrap 5
- **Database**: SQLite with SQLAlchemy ORM
- **Storage**: Local filesystem for configurations with database metadata
- **System Integration**: Subprocess module for WireGuard, IPTables, and system commands
- **Authentication**: Flask-Login with Werkzeug password hashing
- **Monitoring**: Background threading for real-time monitoring
- **Email**: SMTP integration for alert notifications

## Installation

### System Requirements
- Ubuntu/Debian-based system
- Root/sudo access required
- Python 3.8 or higher
- WireGuard kernel module support

### Quick Installation

**Full Installation** (recommended):
```bash
sudo ./install.sh
```

### Installation Options

1. **Skip Python Package Installation**:
   ```bash
   sudo ./install.sh --skip-pip
   ```

2. **Skip System Dependencies**:
   ```bash
   sudo ./install.sh --skip-dependencies
   ```

3. **Skip Both Python and System Dependencies**:
   ```bash
   sudo ./install.sh --skip-all
   ```

### What the Installation Does

The installation script automatically:
- Installs required system packages (WireGuard, IPTables, networking tools)
- Enables IP forwarding and configures networking
- Sets up application directory structure in `/opt/wireguard-gateway/`
- Configures proper user permissions and file ownership
- Creates Python virtual environment and installs dependencies
- Initializes databases and creates default admin user
- Sets up systemd service for automatic startup
- Configures logging and monitoring services

## Getting Started

### First Login
1. Access the application at `http://your-server:5000`
2. Login with default credentials:
   - **Username**: `admin`
   - **Password**: `admin123`
3. You'll be automatically redirected to change your password
4. Set a secure password (minimum 8 characters)

### Basic Workflow
1. **Upload Client Configs**: Upload `.conf` files through the web interface
2. **Activate Clients**: Activate VPN tunnels with automatic network configuration
3. **Monitor Status**: View real-time connection status and handshake information
4. **Configure Alerts**: Set up email notifications for disconnected clients
5. **Setup DDNS**: Configure dynamic DNS monitoring for automatic reconnection

## Configuration

### Email Alerts Setup
1. Navigate to "Email Settings" in the web interface
2. Configure SMTP server details:
   - SMTP Host and Port
   - Authentication credentials
   - Sender email address
3. Set alert preferences and test email delivery

### DDNS Monitoring Configuration
1. Go to "DDNS Monitoring" section
2. Add hostnames to monitor for IP changes
3. Configure auto-reconnect settings
4. Set monitoring intervals and retry limits

### Backup Configuration
1. Access "Backup & Restore" from the main menu
2. Schedule automatic backups or create manual backups
3. Download backup files for external storage
4. Test restore procedures in development environment

## API Documentation

### Authentication
All API endpoints require authentication. Use session-based authentication through the web interface or implement API key authentication.

### Key Endpoints
- `GET /api/clients` - List all clients with status
- `POST /api/clients/{id}/activate` - Activate a client
- `POST /api/clients/{id}/deactivate` - Deactivate a client
- `GET /api/monitoring/status` - Get real-time monitoring data
- `GET /api/auto-reconnect/status` - Get DDNS monitoring status
- `POST /api/backup/create` - Create system backup
- `POST /api/system/reboot` - Reboot server (admin only)

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yrks12/WireGuard-Gateway-UI.git
   cd WireGuard-Gateway-UI
   ```

2. **Set up Python virtual environment**:
   ```bash
   python -m venv env
   source env/bin/activate  # Note: Uses 'env' not 'venv'
   pip install -r requirements.txt
   ```

3. **Run development server**:
   ```bash
   python run.py
   ```

4. **Access the application**:
   Open `http://localhost:5000` in your browser

### Development Notes
- Uses non-standard `env/` directory for virtual environment
- Development runs from current directory
- Production runs from `/opt/wireguard-gateway/`
- Always run `sudo ./install.sh --skip-dependencies` to deploy changes

## Deployment

### Production Deployment
- **Application Location**: `/opt/wireguard-gateway/`
- **Service Control**: `systemctl start/stop/restart wireguard-gateway`
- **Logs**: `/var/log/wireguard-gateway/wireguard.log`
- **Database**: `/opt/wireguard-gateway/instance/`

### Updating Production
```bash
# Deploy code changes
sudo ./install.sh --skip-dependencies

# Restart service if needed
sudo systemctl restart wireguard-gateway
```

## Troubleshooting

### Common Issues
1. **Permission Errors**: Ensure proper file ownership and database permissions
2. **Service Won't Start**: Check logs and verify Python dependencies
3. **VPN Not Connecting**: Verify WireGuard kernel module and IP forwarding
4. **Email Alerts Not Working**: Test SMTP settings and check firewall rules

### Log Locations
- **Application Logs**: `/var/log/wireguard-gateway/wireguard.log`
- **System Logs**: `journalctl -u wireguard-gateway`
- **WireGuard Logs**: `sudo wg show` and `journalctl -u wg-quick@*`

## Security Considerations

- **Default Credentials**: Change default admin password immediately
- **File Permissions**: Restrict access to configuration files
- **Network Security**: Configure firewall rules appropriately
- **Regular Updates**: Keep system and dependencies updated
- **Backup Security**: Store backups securely and encrypt sensitive data

## Contributing

### Branching Strategy
- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Feature development branches
- `bugfix/*`: Bug fix branches
- `hotfix/*`: Critical production fixes

### Development Guidelines
1. Create feature branches from `develop`
2. Follow existing code style and patterns
3. Add tests for new functionality
4. Update documentation for new features
5. Submit pull requests for review

## Support & Development

**Developed by YairTech** - For professional support, custom development, or enterprise features:

- 🌐 **Website**: [www.yairtech.co.uk](https://www.yairtech.co.uk)
- 📧 **Contact**: Professional support and custom development available
- 🎯 **Specializations**: Business automation, CRM development, AI integration, dashboards
- 📊 **Case Studies**: [View our work](https://www.yairtech.co.uk/case-studies)

### Enterprise Features Available
- Custom integrations with existing infrastructure
- Advanced monitoring and alerting systems
- Multi-tenant deployments
- Custom authentication providers
- High-availability configurations
- Professional support and maintenance

## License

This project is developed and maintained by YairTech. For licensing information and commercial use, please contact [YairTech](https://www.yairtech.co.uk).

---

**Building the future of network automation - One connection at a time.**