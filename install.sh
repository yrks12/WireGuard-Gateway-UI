#!/bin/bash
set -e

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}${BOLD}=== $1 ===${NC}\n"
}

# Function to print status messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to print error messages
print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root"
    exit 1
fi

# Parse arguments
SKIP_PIP=false
SKIP_DEPENDENCIES=false
DEFAULT_USERNAME="admin"
DEFAULT_PASSWORD="admin123"  # This will be forced to change on first login
MIGRATE_ONLY=false
CLEANUP_CONFLICTS=false

for arg in "$@"
do
    case $arg in
        --skip-pip)
        SKIP_PIP=true
        print_warning "Skipping pip installation"
        shift
        ;;
        --skip-dependencies)
        SKIP_DEPENDENCIES=true
        print_warning "Skipping system dependencies installation"
        shift
        ;;
        --skip-all)
        SKIP_PIP=true
        SKIP_DEPENDENCIES=true
        print_warning "Skipping all installations"
        shift
        ;;
        --migrate)
        MIGRATE_ONLY=true
        print_warning "Running database migration only"
        shift
        ;;
        --cleanup-conflicts)
        CLEANUP_CONFLICTS=true
        print_warning "Will clean up WireGuard conflicts during installation"
        shift
        ;;
    esac
done

# Handle migration-only mode
if [ "$MIGRATE_ONLY" = true ]; then
    print_header "Database Migration"
    
    # Check if the application is installed
    if [ ! -d "/opt/wireguard-gateway" ]; then
        print_error "WireGuard Gateway is not installed. Please run installation first."
        exit 1
    fi
    
    # Run migration script
    print_status "Running database migration and conflict cleanup..."
    /opt/wireguard-gateway/venv/bin/python << 'EOF'
import sys
sys.path.insert(0, '/opt/wireguard-gateway')
from app import create_app, db
from app.models.client import Client
import subprocess
import os

app = create_app()
with app.app_context():
    print("=== WireGuard Interface and Database Cleanup ===")
    
    # Step 1: Get active WireGuard interfaces
    try:
        result = subprocess.run(['wg', 'show', 'interfaces'], capture_output=True, text=True)
        active_interfaces = result.stdout.strip().split() if result.returncode == 0 else []
        print(f"Found {len(active_interfaces)} active WireGuard interfaces: {active_interfaces}")
    except Exception as e:
        print(f"Error getting WireGuard interfaces: {e}")
        active_interfaces = []
    
    # Step 2: Clean up orphaned interfaces (active but not in database)
    orphaned_cleaned = 0
    if active_interfaces:
        from app.services.config_storage import ConfigStorageService
        config_storage = ConfigStorageService('/opt/wireguard-gateway/instance/configs', '/opt/wireguard-gateway/instance/configs.db')
        db_clients = config_storage.list_clients()
        db_interface_names = [os.path.splitext(os.path.basename(client['config_path']))[0] for client in db_clients]
        
        for interface in active_interfaces:
            if interface not in db_interface_names:
                print(f"Found orphaned interface: {interface} (not in database)")
                try:
                    # First try wg-quick down (in case config exists)
                    result = subprocess.run(['wg-quick', 'down', interface], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Successfully brought down orphaned interface with wg-quick: {interface}")
                        orphaned_cleaned += 1
                    else:
                        # If wg-quick fails (no config file), use ip link delete
                        print(f"wg-quick failed for {interface}, trying ip link delete...")
                        result = subprocess.run(['ip', 'link', 'delete', interface], capture_output=True, text=True)
                        if result.returncode == 0:
                            print(f"Successfully removed orphaned interface with ip link delete: {interface}")
                            orphaned_cleaned += 1
                            
                            # Clean up any orphaned iptables rules for this interface
                            try:
                                print(f"Cleaning up orphaned iptables rules for {interface}...")
                                # Get potential subnets that might be associated with this interface
                                # Try common patterns first, then clean up any rules containing the interface name
                                cleanup_cmds = [
                                    ['iptables', '-t', 'nat', '-L', 'POSTROUTING', '-v', '-n'],
                                    ['iptables', '-L', 'FORWARD', '-v', '-n']
                                ]
                                
                                for cmd in cleanup_cmds:
                                    list_result = subprocess.run(cmd, capture_output=True, text=True)
                                    if list_result.returncode == 0:
                                        # Look for rules containing our interface name
                                        for line in list_result.stdout.split('\n'):
                                            if interface in line:
                                                print(f"Found iptables rule for {interface}: {line.strip()}")
                                
                                # Remove any FORWARD rules containing the interface name
                                forward_cleanup = subprocess.run(['iptables', '-S', 'FORWARD'], capture_output=True, text=True)
                                if forward_cleanup.returncode == 0:
                                    for line in forward_cleanup.stdout.split('\n'):
                                        if interface in line and line.startswith('-A'):
                                            # Convert -A to -D to delete the rule
                                            delete_rule = line.replace('-A', '-D', 1)
                                            delete_cmd = ['iptables'] + delete_rule.split()[1:]
                                            subprocess.run(delete_cmd, capture_output=True, text=True)
                                            print(f"Removed iptables rule: {' '.join(delete_cmd)}")
                                
                                # Remove any NAT rules containing the interface name  
                                nat_cleanup = subprocess.run(['iptables', '-t', 'nat', '-S', 'POSTROUTING'], capture_output=True, text=True)
                                if nat_cleanup.returncode == 0:
                                    for line in nat_cleanup.stdout.split('\n'):
                                        if interface in line and line.startswith('-A'):
                                            delete_rule = line.replace('-A', '-D', 1)
                                            delete_cmd = ['iptables', '-t', 'nat'] + delete_rule.split()[1:]
                                            subprocess.run(delete_cmd, capture_output=True, text=True)
                                            print(f"Removed NAT rule: {' '.join(delete_cmd)}")
                                            
                            except Exception as e:
                                print(f"Error cleaning up iptables rules for {interface}: {e}")
                        else:
                            print(f"Failed to remove {interface} with both methods: {result.stderr}")
                except Exception as e:
                    print(f"Error removing {interface}: {e}")
    
    # Step 3: Get all clients from database
    all_clients = Client.query.all()
    print(f"Found {len(all_clients)} clients in database")
    
    # Step 4: Clean up stale database entries
    stale_count = 0
    for client in all_clients:
        # Check if the client's interface exists
        if client.name not in active_interfaces and client.status == 'active':
            print(f"Marking stale database client as inactive: {client.name}")
            client.status = 'inactive'
            stale_count += 1
    
    # Step 5: Check for duplicate clients with same public key
    from collections import defaultdict
    clients_by_key = defaultdict(list)
    for client in all_clients:
        clients_by_key[client.public_key].append(client)
    
    duplicates_removed = 0
    for public_key, client_list in clients_by_key.items():
        if len(client_list) > 1:
            print(f"Found {len(client_list)} clients with same public key {public_key[:16]}...")
            # Keep the most recent, remove others
            client_list.sort(key=lambda x: x.created_at, reverse=True)
            to_keep = client_list[0]
            to_remove = client_list[1:]
            
            print(f"Keeping: {to_keep.name} (created: {to_keep.created_at})")
            for client in to_remove:
                print(f"Removing duplicate: {client.name} (created: {client.created_at})")
                # Remove config file if it exists
                if os.path.exists(client.config_path):
                    try:
                        os.remove(client.config_path)
                        print(f"Removed config file: {client.config_path}")
                    except Exception as e:
                        print(f"Error removing config file {client.config_path}: {e}")
                
                db.session.delete(client)
                duplicates_removed += 1
    
    # Step 6: Check for routing conflicts
    route_conflicts = 0
    try:
        # Get current routes
        result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True)
        if result.returncode == 0:
            routes = result.stdout
            # Look for routes that might conflict with common WireGuard subnets
            problem_routes = []
            for line in routes.split('\n'):
                if 'dev bs_' in line or 'dev cer_' in line:
                    problem_routes.append(line.strip())
            
            if problem_routes:
                print(f"Found {len(problem_routes)} existing WireGuard routes:")
                for route in problem_routes:
                    print(f"  {route}")
                route_conflicts = len(problem_routes)
    except Exception as e:
        print(f"Error checking routes: {e}")
    
    # Commit database changes
    db.session.commit()
    
    print("\n=== Cleanup Summary ===")
    print(f"Orphaned interfaces cleaned: {orphaned_cleaned}")
    print(f"Stale database entries updated: {stale_count}")
    print(f"Duplicate clients removed: {duplicates_removed}")
    print(f"Existing WireGuard routes found: {route_conflicts}")
    print("Migration and cleanup completed!")
EOF
    
    print_status "Database migration completed!"
    exit 0
fi

print_header "WireGuard Gateway Installation"
print_status "Starting installation process..."

# Create wireguard user and group if they don't exist
print_status "Setting up WireGuard user and groups..."
if ! getent group wireguard >/dev/null; then
    groupadd wireguard
fi

if ! getent passwd wireguard >/dev/null; then
    useradd -g wireguard -s /bin/false wireguard
fi

# Add wireguard user and root to necessary groups
usermod -a -G sudo wireguard
usermod -a -G netdev wireguard
usermod -a -G wireguard root

# Clean up existing WireGuard conflicts if requested
if [ "$CLEANUP_CONFLICTS" = true ]; then
    print_header "Cleaning Up WireGuard Conflicts"
    print_status "Stopping any existing WireGuard interfaces..."
    
    # Get list of active WireGuard interfaces
    if command -v wg >/dev/null 2>&1; then
        ACTIVE_INTERFACES=$(wg show interfaces 2>/dev/null || true)
        if [ ! -z "$ACTIVE_INTERFACES" ]; then
            print_warning "Found active WireGuard interfaces: $ACTIVE_INTERFACES"
            for interface in $ACTIVE_INTERFACES; do
                print_status "Bringing down interface: $interface"
                # Try wg-quick first, then ip link delete if that fails
                if ! wg-quick down "$interface" 2>/dev/null; then
                    print_warning "wg-quick failed for $interface, using ip link delete"
                    ip link delete "$interface" 2>/dev/null || true
                fi
            done
        else
            print_status "No active WireGuard interfaces found"
        fi
    fi
    
    # Clean up any leftover routes
    print_status "Cleaning up WireGuard routes..."
    ip route show | grep -E "dev (bs_|cer_)" | while read route; do
        print_warning "Removing route: $route"
        ip route del $route 2>/dev/null || true
    done
    
    # Clean up any leftover iptables rules
    print_status "Cleaning up WireGuard iptables rules..."
    # Get list of rules that might be related to WireGuard interfaces
    iptables -S FORWARD | grep -E "(bs_|cer_)" | while read rule; do
        if [[ $rule == -A* ]]; then
            delete_rule=$(echo "$rule" | sed 's/-A /-D /')
            print_warning "Removing iptables rule: $delete_rule"
            iptables $delete_rule 2>/dev/null || true
        fi
    done
    
    iptables -t nat -S POSTROUTING | grep -E "(bs_|cer_)" | while read rule; do
        if [[ $rule == -A* ]]; then
            delete_rule=$(echo "$rule" | sed 's/-A /-D /')
            print_warning "Removing NAT rule: $delete_rule"
            iptables -t nat $delete_rule 2>/dev/null || true
        fi
    done
    
    print_status "Conflict cleanup completed"
fi

# Install required packages if not skipped
if [ "$SKIP_DEPENDENCIES" = false ]; then
    print_header "Installing System Dependencies"
    print_status "Updating package lists..."
    apt-get update
    
    print_status "Installing required packages..."
    apt-get install -y \
        wireguard \
        wireguard-tools \
        resolvconf \
        iptables-persistent \
        netfilter-persistent \
        python3 \
        python3-venv \
        python3-pip \
        python3-dev \
        net-tools \
        iproute2 \
        dnsutils \
        iputils-ping

    print_status "Enabling IP forwarding..."
    echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf
    sysctl -p
else
    print_warning "Skipping system dependencies installation as requested"
fi

# Define directories
INSTALL_DIR="/opt/wireguard-gateway"
INSTANCE_DIR="$INSTALL_DIR/instance"
CONFIGS_DIR="$INSTANCE_DIR/configs"
PENDING_DIR="$INSTANCE_DIR/pending_configs"
DB_DIR="/var/lib/wireguard-gateway"
LOG_DIR="/var/log/wireguard-gateway"
LOG_FILE="$LOG_DIR/wireguard.log"
DB_FILE="$DB_DIR/wireguard.db"

# Create directories
print_header "Creating Installation Directories"
print_status "Setting up directory structure..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTANCE_DIR
mkdir -p $CONFIGS_DIR
mkdir -p $PENDING_DIR
mkdir -p $DB_DIR
mkdir -p $LOG_DIR
mkdir -p /etc/wireguard

print_status "Setting up log file..."
touch $LOG_FILE
chmod 666 $LOG_FILE

print_status "Setting up database file..."

# Backup email settings before removing database
EMAIL_BACKUP_FILE="/tmp/wireguard-gateway-email-backup.json"
if [ -f "$DB_FILE" ]; then
    print_status "Backing up email settings..."
    python3 scripts/backup-restore-email.py backup "$DB_FILE" "$EMAIL_BACKUP_FILE" || true
fi

rm -f $DB_FILE
touch $DB_FILE
chmod 666 $DB_FILE

print_status "Configuring WireGuard directory permissions..."
chown wireguard:wireguard /etc/wireguard
chmod 750 /etc/wireguard

# Copy files
print_header "Installing Application Files"
print_status "Copying application files to $INSTALL_DIR..."
cp -r app $INSTALL_DIR/
cp -r scripts $INSTALL_DIR/
cp requirements.txt $INSTALL_DIR/
cp run.py $INSTALL_DIR/

# Ensure the restore script is copied properly
if [ -f "scripts/restore-interfaces.py" ]; then
    cp scripts/restore-interfaces.py $INSTALL_DIR/scripts/
    print_status "Copied restore-interfaces.py script"
else
    print_warning "restore-interfaces.py not found in scripts directory"
fi

# Create virtual environment and install dependencies
print_header "Setting Up Python Environment"
print_status "Creating Python virtual environment..."
cd $INSTALL_DIR
python3 -m venv venv

if [ "$SKIP_PIP" = false ]; then
    print_status "Installing Python dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install setuptools  # Add setuptools for pkg_resources
    pip install -r requirements.txt
else
    print_warning "Skipping pip install as requested"
fi

# Create run script
print_header "Creating System Scripts"
print_status "Creating run script..."
cat > /usr/local/bin/wireguard-gateway << EOF
#!/bin/bash
export INSTANCE_PATH="$INSTANCE_DIR"
export DATABASE_URL="sqlite:///$DB_FILE"
export LOG_PATH="$LOG_FILE"
cd $INSTALL_DIR
sudo -u wireguard /bin/bash <<SCRIPT_EOF
source $INSTALL_DIR/venv/bin/activate
python $INSTALL_DIR/run.py
SCRIPT_EOF
EOF

# Set up sudoers entry for wireguard user
print_status "Configuring sudo permissions..."
cat > /etc/sudoers.d/wireguard << EOF
# Allow the wireguard user to run wg-quick commands without password
wireguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick up *
wireguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick down *
wireguard ALL=(ALL) NOPASSWD: /usr/bin/wg show *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/sysctl -w net.ipv4.ip_forward=*
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/sysctl -p
wireguard ALL=(ALL) NOPASSWD: /usr/bin/tee -a /etc/sysctl.conf
wireguard ALL=(ALL) NOPASSWD: /usr/bin/resolvconf -a *
wireguard ALL=(ALL) NOPASSWD: /usr/bin/resolvconf -d *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/iptables -t nat -A POSTROUTING *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/iptables -A FORWARD *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/iptables -t nat -D POSTROUTING *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/iptables -D FORWARD *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/iptables -t nat -L POSTROUTING -v -n
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/iptables -L FORWARD -v -n
wireguard ALL=(ALL) NOPASSWD: /usr/bin/ping -c 1 -W 2 *
wireguard ALL=(ALL) NOPASSWD: /usr/bin/wg show *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/ip route show default
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/ip addr show *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/ip link delete *
wireguard ALL=(ALL) NOPASSWD: /usr/sbin/ip route show
wireguard ALL=(ALL) NOPASSWD: /sbin/reboot
EOF
chmod 440 /etc/sudoers.d/wireguard

# Set permissions
print_header "Setting Permissions"
print_status "Configuring file permissions..."
chmod +x /usr/local/bin/wireguard-gateway
chmod -R 755 $INSTALL_DIR
chmod -R 750 $CONFIGS_DIR
chmod -R 750 $PENDING_DIR
chmod -R 777 $DB_DIR
chmod -R 777 $LOG_DIR

# Set ownership
print_status "Setting file ownership..."
chown -R wireguard:wireguard $INSTALL_DIR
chown -R wireguard:wireguard $INSTANCE_DIR
chown -R wireguard:wireguard $DB_DIR
chown -R wireguard:wireguard $LOG_DIR

# Initialize database as wireguard user
print_header "Initializing Database"
print_status "Creating database tables and default admin user..."
sudo -u wireguard /bin/bash <<DB_INIT_EOF
cd $INSTALL_DIR
source venv/bin/activate
python -c "
import os
os.environ['INSTANCE_PATH'] = '$INSTANCE_DIR'
os.environ['DATABASE_URL'] = 'sqlite:///$DB_FILE'
os.environ['LOG_PATH'] = '$LOG_FILE'

from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash

# Create the Flask app
app = create_app()

# Create the database tables and admin user within the app context
with app.app_context():
    # Create database tables
    db.create_all()
    
    # Create default admin user if it doesn't exist
    if not User.query.filter_by(username='$DEFAULT_USERNAME').first():
        admin = User(
            username='$DEFAULT_USERNAME',
            password=generate_password_hash('$DEFAULT_PASSWORD'),
            must_change_password=True
        )
        db.session.add(admin)
        db.session.commit()
"
DB_INIT_EOF

# Ensure database files have correct ownership and permissions
chown wireguard:wireguard $DB_FILE
chmod 666 $DB_FILE

# Also ensure configs.db has correct permissions
CONFIGS_DB_FILE="$INSTANCE_DIR/configs.db"
if [ -f "$CONFIGS_DB_FILE" ]; then
    chown wireguard:wireguard $CONFIGS_DB_FILE
    chmod 666 $CONFIGS_DB_FILE
fi

# Restore email settings if backup exists
if [ -f "$EMAIL_BACKUP_FILE" ]; then
    print_status "Restoring email settings from backup..."
    # We're already in $INSTALL_DIR at this point
    source venv/bin/activate
    python scripts/backup-restore-email.py restore "$DB_FILE" "$EMAIL_BACKUP_FILE"
    if [ $? -eq 0 ]; then
        print_status "Email settings restored successfully"
    else
        print_warning "Failed to restore email settings"
    fi
    deactivate
fi

# Set up config file permissions
print_status "Setting up config file permissions..."
find $CONFIGS_DIR -type f -name "*.conf" -exec chmod 640 {} \;
find $PENDING_DIR -type f -name "*.conf" -exec chmod 640 {} \;

# Set up restoration scripts
print_status "Setting up interface restoration scripts..."
SCRIPTS_DIR="$INSTALL_DIR/scripts"
mkdir -p $SCRIPTS_DIR
chown wireguard:wireguard $SCRIPTS_DIR
chmod 755 $SCRIPTS_DIR

# Set permissions for restoration scripts
if [ -f "$SCRIPTS_DIR/restore-interfaces.py" ]; then
    chown wireguard:wireguard "$SCRIPTS_DIR/restore-interfaces.py"
    chmod 755 "$SCRIPTS_DIR/restore-interfaces.py"
fi

if [ -f "$SCRIPTS_DIR/restore-interfaces.sh" ]; then
    chown wireguard:wireguard "$SCRIPTS_DIR/restore-interfaces.sh"
    chmod 755 "$SCRIPTS_DIR/restore-interfaces.sh"
fi

# Create systemd service
print_header "Setting Up System Service"
print_status "Creating systemd service file..."
cat > /etc/systemd/system/wireguard-gateway.service << EOF
[Unit]
Description=WireGuard Gateway Service
After=network.target

[Service]
Type=simple
User=wireguard
Group=wireguard
Environment=INSTANCE_PATH=$INSTANCE_DIR
Environment=DATABASE_URL=sqlite:///$DB_FILE
Environment=LOG_PATH=$LOG_FILE
WorkingDirectory=$INSTALL_DIR
ExecStartPre=$INSTALL_DIR/scripts/restore-interfaces.sh
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
print_status "Enabling and starting WireGuard Gateway service..."
systemctl daemon-reload
systemctl enable wireguard-gateway
systemctl start wireguard-gateway

print_header "Installation Complete!"
echo -e "${GREEN}${BOLD}WireGuard Gateway has been successfully installed!${NC}"
echo -e "\n${BOLD}Service Information:${NC}"
echo -e "  • Service Status: ${GREEN}Active${NC}"
echo -e "  • Service Name: wireguard-gateway"
echo -e "  • Installation Directory: $INSTALL_DIR"
echo -e "\n${BOLD}Default Credentials:${NC}"
echo -e "  • Username: ${YELLOW}$DEFAULT_USERNAME${NC}"
echo -e "  • Password: ${YELLOW}$DEFAULT_PASSWORD${NC}"
echo -e "  • Note: You will be required to change the password on first login"
echo -e "\n${BOLD}Service Management:${NC}"
echo -e "  • Check status: ${BLUE}systemctl status wireguard-gateway${NC}"
echo -e "  • Start service: ${BLUE}systemctl start wireguard-gateway${NC}"
echo -e "  • Stop service: ${BLUE}systemctl stop wireguard-gateway${NC}"
echo -e "  • Restart service: ${BLUE}systemctl restart wireguard-gateway${NC}"
