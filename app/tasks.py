import threading
import time
import logging
from flask import current_app
from app.services.wireguard import WireGuardService
from app.services.wireguard_monitor import WireGuardMonitor
from datetime import datetime

logger = logging.getLogger(__name__)

def monitor_wireguard(app):
    """Monitor WireGuard peers and update their status."""
    while True:
        try:
            with app.app_context():
                # Get all clients from config storage
                clients = app.config_storage.list_clients()
                
                # Update status for each client
                for client in clients:
                    try:
                        # Only monitor clients that are marked as active in the database
                        client_status = client.get('status', 'unknown')
                        logger.info(f"Checking client {client.get('name', 'Unknown')} with status: '{client_status}'")
                        if client_status != 'active':
                            logger.info(f"Skipping monitoring for inactive client {client.get('name', 'Unknown')} (status: {client_status})")
                            continue
                        
                        # Get interface name from config path
                        import os
                        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
                        
                        # Use WireGuardMonitor to check interface status and alerts
                        peers = WireGuardMonitor.check_interface(interface_name)
                        
                        # Check for disconnect alerts
                        WireGuardMonitor.check_and_alert(
                            interface_name, 
                            client.get('name', 'Unknown'),
                            client['id'],
                            app.config_storage
                        )
                        
                        # Update client status based on peer connection
                        if peers:
                            # Check if any peer is connected
                            is_connected = any(peers.values())
                            new_status = 'active' if is_connected else 'inactive'
                            
                            # Update last handshake time if available
                            last_handshake = None
                            for peer_key, connected in peers.items():
                                if connected and peer_key in WireGuardMonitor._last_handshakes:
                                    last_handshake = WireGuardMonitor._last_handshakes[peer_key]
                                    break
                            
                            # Update client status in storage
                            app.config_storage.update_client_status(client['id'], new_status, last_handshake)
                        else:
                            # No peers found - interface doesn't exist, mark as inactive
                            if client['status'] != 'inactive':
                                logger.info(f"Interface {interface_name} not found, marking client {client.get('name', 'Unknown')} as inactive")
                                app.config_storage.update_client_status(client['id'], 'inactive')
                        
                    except Exception as e:
                        # Log error but don't spam if it's the same "No such device" error
                        error_msg = str(e)
                        if "No such device" not in error_msg:
                            logger.error(f"Error updating status for client {client.get('name', 'Unknown')}: {error_msg}")
                        elif client['status'] != 'inactive':
                            # Only log "No such device" if the client is not already marked inactive
                            logger.info(f"Interface for client {client.get('name', 'Unknown')} not found, marking as inactive")
                            app.config_storage.update_client_status(client['id'], 'inactive')
                
        except Exception as e:
            logger.error(f"Error in monitoring task: {str(e)}")
            
        # Sleep for 30 seconds before next update
        time.sleep(30)

def start(app):
    """Start the WireGuard monitoring task in a background thread."""
    global monitor_task
    monitor_task = threading.Thread(target=monitor_wireguard, args=(app,), daemon=True)
    monitor_task.start()
    logging.info("Started WireGuard monitoring task")

# Global monitor thread
monitor_task = None 