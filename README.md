# WireGuard Gateway Web App

A web application for managing WireGuard VPN tunnels, automating NAT/forwarding rules, and monitoring gateway performance.

## Features

- Upload and validate WireGuard client configurations
- Activate/deactivate VPN tunnels
- Automate NAT and forwarding rules
- Generate router route instructions
- Monitor tunnel health and gateway performance

## Tech Stack

- Backend: Python 3.8 (Flask) with Jinja2 templates
- Frontend: HTML, CSS, JavaScript
- Storage: Local FS for .conf files; SQLite/JSON for metadata
- System Integration: subprocess module for wg-quick and iptables

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