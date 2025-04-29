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
    esac
done

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
cp requirements.txt $INSTALL_DIR/
cp run.py $INSTALL_DIR/

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

# Ensure database file has correct ownership and permissions
chown wireguard:wireguard $DB_FILE
chmod 666 $DB_FILE

# Set up config file permissions
print_status "Setting up config file permissions..."
find $CONFIGS_DIR -type f -name "*.conf" -exec chmod 640 {} \;
find $PENDING_DIR -type f -name "*.conf" -exec chmod 640 {} \;

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
