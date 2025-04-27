#!/bin/bash
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Parse arguments
SKIP_PIP=false
SKIP_DEPENDENCIES=false
for arg in "$@"
do
    case $arg in
        --skip-pip)
        SKIP_PIP=true
        shift
        ;;
        --skip-dependencies)
        SKIP_DEPENDENCIES=true
        shift
        ;;
        --skip-all)
        SKIP_PIP=true
        SKIP_DEPENDENCIES=true
        shift
        ;;
    esac
done

# Install required packages if not skipped
if [ "$SKIP_DEPENDENCIES" = false ]; then
    echo "Installing required packages..."
    apt-get update
    apt-get install -y \
        wireguard \
        wireguard-tools \
        resolvconf \
        iptables-persistent \
        netfilter-persistent \
        python3 \
        python3-venv \
        python3-pip \
        net-tools \
        iproute2 \
        dnsutils \
        iputils-ping

    # Enable IP forwarding
    echo "Enabling IP forwarding..."
    echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf
    sysctl -p
else
    echo "Skipping system dependencies installation as requested"
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
echo "Creating installation directories..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTANCE_DIR
mkdir -p $CONFIGS_DIR
mkdir -p $PENDING_DIR
mkdir -p $DB_DIR
mkdir -p $LOG_DIR
mkdir -p /etc/wireguard  # Create wireguard config directory

# Create log file with proper permissions
touch $LOG_FILE
chmod 666 $LOG_FILE  # Allow read/write for all users

# Create database file with proper permissions
rm -f $DB_FILE  # Remove existing database if any
touch $DB_FILE
chmod 666 $DB_FILE  # Allow read/write for all users

# Set permissions for wireguard directory
chown wireguard:wireguard /etc/wireguard
chmod 750 /etc/wireguard  # Allow wireguard group to read and execute

# Copy files
echo "Copying application files..."
cp -r app $INSTALL_DIR/
cp requirements.txt $INSTALL_DIR/
cp run.py $INSTALL_DIR/

# Create virtual environment and install dependencies
echo "Setting up Python virtual environment..."
cd $INSTALL_DIR
python3 -m venv venv

if [ "$SKIP_PIP" = false ]; then
    echo "Installing Python dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "Skipping pip install as requested"
fi

# Create run script
echo "Creating run script..."
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

# Create wireguard user and group if they don't exist
if ! getent group wireguard >/dev/null; then
    groupadd wireguard
fi

if ! getent passwd wireguard >/dev/null; then
    useradd -g wireguard -s /bin/false wireguard
fi

# Add wireguard user and root to necessary groups
usermod -a -G sudo wireguard
usermod -a -G netdev wireguard
usermod -a -G wireguard root  # Add root to wireguard group

# Set up sudoers entry for wireguard user
echo "Setting up sudoers entry..."
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
EOF
chmod 440 /etc/sudoers.d/wireguard

# Set permissions
echo "Setting permissions..."
chmod +x /usr/local/bin/wireguard-gateway
chmod -R 755 $INSTALL_DIR
chmod -R 750 $CONFIGS_DIR  # Allow wireguard group to access configs
chmod -R 750 $PENDING_DIR  # Allow wireguard group to access pending configs
chmod -R 777 $DB_DIR
chmod -R 777 $LOG_DIR

# Set ownership
chown -R wireguard:wireguard $INSTALL_DIR
chown -R wireguard:wireguard $INSTANCE_DIR
chown -R wireguard:wireguard $DB_DIR
chown -R wireguard:wireguard $LOG_DIR

# Initialize database as wireguard user
echo "Initializing database..."
sudo -u wireguard /bin/bash <<DB_INIT_EOF
cd $INSTALL_DIR
source venv/bin/activate
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app import db
    db.create_all()
"
DB_INIT_EOF

# Ensure database file has correct ownership and permissions
chown wireguard:wireguard $DB_FILE
chmod 666 $DB_FILE

# Set up config file permissions
echo "Setting up config file permissions..."
find $CONFIGS_DIR -type f -name "*.conf" -exec chmod 640 {} \;  # Set config files to 640 (readable by group)
find $PENDING_DIR -type f -name "*.conf" -exec chmod 640 {} \;  # Set pending config files to 640 (readable by group)

# Create systemd service
echo "Creating systemd service..."
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
echo "Enabling and starting WireGuard Gateway service..."
systemctl daemon-reload
systemctl enable wireguard-gateway
systemctl start wireguard-gateway

echo "Installation complete!"
echo "The WireGuard Gateway service has been installed and started."
echo "You can manage it using: systemctl status/start/stop/restart wireguard-gateway"
