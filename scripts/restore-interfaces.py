#!/usr/bin/env python3
"""
WireGuard Interface Restoration Script

This script restores active WireGuard interfaces and their iptables rules after system reboot.
It queries the database for clients that were active before reboot and restores:
1. WireGuard interfaces (wg-quick up)
2. iptables NAT and FORWARD rules
3. IP forwarding system setting

Usage: Called automatically by systemd service on boot
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import project modules
from app.services.wireguard import WireGuardService
from app.services.iptables_manager import IptablesManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/wireguard-gateway/restore.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InterfaceRestorer:
    """Service for restoring WireGuard interfaces and iptables rules after reboot."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_active_clients(self):
        """Get list of clients that were active before reboot."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, name, config_path, subnet, public_key, status
                    FROM client
                    WHERE status = 'active'
                """)
                
                clients = []
                for row in cursor.fetchall():
                    clients.append({
                        'id': row[0],
                        'name': row[1],
                        'config_path': row[2],
                        'subnet': row[3],
                        'public_key': row[4],
                        'status': row[5]
                    })
                
                return clients
                
        except Exception as e:
            logger.error(f"Failed to query active clients: {e}")
            return []
    
    def enable_ip_forwarding(self):
        """Enable IP forwarding system-wide."""
        try:
            import subprocess
            result = subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=1'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("IP forwarding enabled")
                return True
            else:
                logger.error(f"Failed to enable IP forwarding: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error enabling IP forwarding: {e}")
            return False
    
    def restore_client_interface(self, client):
        """Restore a single client's WireGuard interface and iptables rules."""
        client_name = client['name']
        config_path = client['config_path']
        subnet = client['subnet']
        
        logger.info(f"Restoring client: {client_name}")
        
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(config_path))[0]
        
        try:
            # 1. Activate WireGuard interface
            logger.info(f"Activating WireGuard interface: {interface_name}")
            success, error = WireGuardService.activate_client(config_path)
            if not success:
                logger.error(f"Failed to activate {client_name}: {error}")
                return False
            
            # 2. Set up iptables rules
            logger.info(f"Setting up iptables rules for subnet: {subnet}")
            success, error = IptablesManager.setup_forwarding(interface_name, subnet)
            if not success:
                logger.error(f"Failed to setup forwarding for {client_name}: {error}")
                # Try to deactivate the interface since iptables failed
                WireGuardService.deactivate_client(config_path)
                return False
            
            logger.info(f"Successfully restored client: {client_name}")
            return True
            
        except Exception as e:
            logger.error(f"Exception restoring {client_name}: {e}")
            return False
    
    def update_client_status(self, client_id, status):
        """Update client status in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE client 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, client_id))
                logger.info(f"Updated client {client_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update client status: {e}")
    
    def restore_all_interfaces(self):
        """Main restoration process."""
        logger.info("Starting WireGuard interface restoration...")
        
        # 1. Enable IP forwarding
        if not self.enable_ip_forwarding():
            logger.error("Failed to enable IP forwarding, continuing anyway...")
        
        # 2. Get active clients
        active_clients = self.get_active_clients()
        if not active_clients:
            logger.info("No active clients found to restore")
            return True
        
        logger.info(f"Found {len(active_clients)} active clients to restore")
        
        # 3. Restore each client
        restored_count = 0
        failed_count = 0
        
        for client in active_clients:
            if self.restore_client_interface(client):
                restored_count += 1
            else:
                failed_count += 1
                # Mark failed clients as inactive
                self.update_client_status(client['id'], 'inactive')
        
        # 4. Log summary
        logger.info(f"Restoration complete: {restored_count} successful, {failed_count} failed")
        
        if failed_count > 0:
            logger.warning(f"{failed_count} clients failed to restore and were marked inactive")
        
        return failed_count == 0

def main():
    """Main entry point."""
    # Get database path from environment or use default
    db_path = os.environ.get('DATABASE_URL', '/var/lib/wireguard-gateway/wireguard.db')
    if db_path.startswith('sqlite:///'):
        db_path = db_path[10:]  # Remove sqlite:/// prefix
    
    logger.info(f"Using database: {db_path}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)
    
    # Create restorer and run
    restorer = InterfaceRestorer(db_path)
    success = restorer.restore_all_interfaces()
    
    if success:
        logger.info("All interfaces restored successfully")
        sys.exit(0)
    else:
        logger.error("Some interfaces failed to restore")
        sys.exit(1)

if __name__ == '__main__':
    main()