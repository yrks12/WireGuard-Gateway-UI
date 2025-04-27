import threading
import time
import logging
from flask import current_app
from app.services.wireguard_monitor import WireGuardMonitor

logger = logging.getLogger(__name__)

class MonitorTask:
    """Background task for monitoring WireGuard interfaces."""
    
    def __init__(self):
        self._running = False
        self._thread = None
        self._check_interval = 60  # Check every minute
    
    def start(self):
        """Start the monitoring task."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()
        logger.info("Started WireGuard monitoring task")
    
    def stop(self):
        """Stop the monitoring task."""
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("Stopped WireGuard monitoring task")
    
    def _run(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Get all active clients
                clients = current_app.config_storage.list_clients()
                
                # Check each active client
                for client in clients:
                    if client.get('status') == 'active':
                        interface = client.get('interface')
                        client_name = client.get('name', 'Unknown')
                        
                        if interface:
                            WireGuardMonitor.check_and_alert(interface, client_name)
                
            except Exception as e:
                logger.error(f"Error in monitoring task: {e}")
            
            # Wait for next check
            time.sleep(self._check_interval)

# Global monitor task instance
monitor_task = MonitorTask() 