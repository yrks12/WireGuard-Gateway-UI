import threading
import time
import logging
from flask import current_app
from app.services.wireguard import WireGuardService
from app.models.client import Client
from app.database import db

logger = logging.getLogger(__name__)

def monitor_wireguard(app):
    """Monitor WireGuard peers and update their status."""
    while True:
        try:
            with app.app_context():
                # Get all clients from database
                clients = Client.query.all()
                
                # Update status for each client
                for client in clients:
                    try:
                        status = WireGuardService.get_peer_status(client.public_key)
                        if status:
                            client.status = status['status']
                            client.last_handshake = status['last_handshake']
                            db.session.add(client)
                        
                    except Exception as e:
                        logging.error(f"Error updating status for client {client.name}: {str(e)}")
                
                # Commit all changes
                db.session.commit()
                
        except Exception as e:
            logging.error(f"Error in monitoring task: {str(e)}")
            
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