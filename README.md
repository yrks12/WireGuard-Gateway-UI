# WireGuard Gateway Web App

A web application for managing WireGuard VPN tunnels, automating NAT/forwarding rules, and monitoring gateway performance.

## Features

- Upload and validate WireGuard client configurations
- Activate/deactivate VPN tunnels
- Automate NAT and forwarding rules
- Generate router route instructions
- Monitor tunnel health and gateway performance
- Secure authentication system

## Tech Stack

- Backend: Python 3.8 (Flask) with Jinja2 templates
- Frontend: HTML, CSS, JavaScript
- Storage: Local FS for .conf files; SQLite/JSON for metadata
- System Integration: subprocess module for wg-quick and iptables
- Authentication: Flask-Login with password hashing

## Installation

### System Requirements
- Ubuntu/Debian-based system
- Root/sudo access
- Python 3.8 or higher

### Installation Options

1. **Full Installation** (recommended):
   ```bash
   sudo ./install.sh
   ```

2. **Skip Python Package Installation**:
   ```bash
   sudo ./install.sh --skip-pip
   ```

3. **Skip System Dependencies**:
   ```bash
   sudo ./install.sh --skip-dependencies
   ```

4. **Skip Both Python and System Dependencies**:
   ```bash
   sudo ./install.sh --skip-all
   ```

The installation script will:
- Install required system packages (unless skipped):
  - WireGuard and tools
  - resolvconf
  - iptables-persistent
  - netfilter-persistent
  - Python and related tools
  - Network utilities
- Enable IP forwarding
- Set up the application directory structure
- Configure necessary permissions
- Create the virtual environment
- Install Python dependencies (unless skipped)
- Initialize the database and create default admin user

## Authentication

The application includes a secure authentication system with the following features:

### Default Credentials
- **Username**: admin
- **Password**: admin123

### Security Features
- Password hashing using Werkzeug
- Forced password change on first login
- Session management
- Login attempt rate limiting
- Password change functionality

### First Login
1. Log in using the default credentials
2. You will be automatically redirected to the password change page
3. Set a new secure password (minimum 8 characters)
4. After changing the password, you'll have full access to the system

### Password Management
- Users can change their password at any time
- Password changes require current password verification
- New passwords must be at least 8 characters long
- Password changes are immediately effective

## Development Setup

1. Clone the repository
2. Set up Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```bash
   flask run
   ```
4. Open http://localhost:5000 in your browser

## Branching Strategy

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Feature branches
- `bugfix/*`: Bug fix branches
- `release/*`: Release preparation branches

### Branch Usage Guidelines

1. Create feature branches from `develop`
2. Merge feature branches back to `develop` after review
3. Create release branches from `develop` for version releases
4. Merge release branches to both `main` and `develop`
5. Hotfixes should branch from `main` and merge back to both `main` and `develop`

## License

[License details to be added] 