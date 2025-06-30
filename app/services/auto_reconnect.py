import logging
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from app.services.wireguard import WireGuardService
from app.services.dns_resolver import DNSResolver
from app.services.config_storage import ConfigStorageService

logger = logging.getLogger(__name__)

class AutoReconnectService:
    """Service for automatically reconnecting WireGuard clients when DNS changes are detected."""
    
    # Store reconnection attempts to prevent infinite loops
    _reconnection_attempts: Dict[str, Dict] = {}
    # Maximum reconnection attempts per client (3 attempts)
    MAX_RECONNECT_ATTEMPTS = 3
    # Cooldown period between reconnection attempts (5 minutes)
    RECONNECT_COOLDOWN = timedelta(minutes=5)
    # Success threshold - if reconnection succeeds, reset attempt counter
    SUCCESS_THRESHOLD = timedelta(minutes=10)
    
    @classmethod
    def handle_dns_change(cls, change_info: Dict, config_storage: ConfigStorageService) -> bool:
        """
        Handle a DNS change by attempting to reconnect the affected client.
        Returns True if reconnection was attempted, False otherwise.
        """
        client_id = change_info['client_id']
        hostname = change_info['hostname']
        previous_ip = change_info['previous_ip']
        current_ip = change_info['current_ip']
        
        logger.info(f"Handling DNS change for client {client_id}: {hostname} {previous_ip} -> {current_ip}")
        
        # Check if we should attempt reconnection
        if not cls._should_attempt_reconnection(client_id):
            logger.info(f"Skipping reconnection for client {client_id} - too many recent attempts")
            return False
        
        # Get client information
        client = config_storage.get_client(client_id)
        if not client:
            logger.error(f"Client {client_id} not found in storage")
            return False
        
        # Attempt reconnection
        success = cls._reconnect_client(client, config_storage)
        
        # Update reconnection tracking
        cls._update_reconnection_tracking(client_id, success)
        
        return True
    
    @classmethod
    def _should_attempt_reconnection(cls, client_id: str) -> bool:
        """
        Check if we should attempt reconnection for a client.
        Prevents infinite reconnection loops.
        """
        attempts = cls._reconnection_attempts.get(client_id, {})
        
        # If no previous attempts, allow reconnection
        if not attempts:
            return True
        
        # Check if we've exceeded max attempts
        attempt_count = attempts.get('count', 0)
        if attempt_count >= cls.MAX_RECONNECT_ATTEMPTS:
            # Check if enough time has passed to reset
            last_attempt = attempts.get('last_attempt')
            if last_attempt and (datetime.now() - last_attempt) > cls.RECONNECT_COOLDOWN:
                # Reset attempt counter
                cls._reconnection_attempts[client_id] = {'count': 0, 'last_attempt': datetime.now()}
                return True
            return False
        
        # Check cooldown period
        last_attempt = attempts.get('last_attempt')
        if last_attempt and (datetime.now() - last_attempt) < cls.RECONNECT_COOLDOWN:
            return False
        
        return True
    
    @classmethod
    def _reconnect_client(cls, client: Dict, config_storage: ConfigStorageService) -> bool:
        """
        Attempt to reconnect a WireGuard client.
        Returns True if reconnection was successful, False otherwise.
        """
        client_id = client['id']
        config_path = client['config_path']
        
        logger.info(f"Attempting to reconnect client {client_id}")
        
        # Log monitoring event
        config_storage.log_monitoring_event(
            client_id, client['name'], "reconnect_attempt",
            f"Starting auto-reconnect attempt", 
            f"Trigger: DNS IP change"
        )
        
        try:
            # Step 1: Deactivate the client
            logger.info(f"Deactivating client {client_id}")
            success, error = WireGuardService.deactivate_client(config_path)
            if not success:
                logger.error(f"Failed to deactivate client {client_id}: {error}")
                return False
            
            # Step 2: Wait a moment for cleanup
            time.sleep(2)
            
            # Step 3: Reactivate the client
            logger.info(f"Reactivating client {client_id}")
            success, error = WireGuardService.activate_client(config_path)
            if not success:
                logger.error(f"Failed to reactivate client {client_id}: {error}")
                return False
            
            # Step 4: Update client status
            config_storage.update_client_status(client_id, 'active')
            
            # Step 5: Trigger initial handshake by pinging client
            try:
                import subprocess
                import re
                
                # Extract client's actual IP from the WireGuard config file
                with open(config_path, 'r') as f:
                    config_content = f.read()
                
                # Look for Address line in [Interface] section
                address_match = re.search(r'Address\s*=\s*([^/\s,]+)', config_content)
                if address_match:
                    client_ip = address_match.group(1).strip()
                    logger.info(f"Triggering handshake for reconnected client {client_id} by pinging {client_ip}")
                    
                    ping_result = subprocess.run(
                        ['sudo', 'ping', '-c', '1', '-W', '2', client_ip],
                        capture_output=True,
                        text=True
                    )
                    
                    if ping_result.returncode == 0:
                        logger.info(f"Successfully pinged reconnected client {client_id} - handshake established")
                        config_storage.log_monitoring_event(
                            client_id, client['name'], "reconnect_handshake_established",
                            f"Handshake established after auto-reconnect",
                            f"Pinged {client_ip}"
                        )
                    else:
                        logger.warning(f"Ping to reconnected client {client_id} failed")
                else:
                    logger.warning(f"Could not extract client IP from config for reconnected client {client_id}")
            except Exception as ping_error:
                logger.warning(f"Error triggering handshake for reconnected client {client_id}: {ping_error}")
            
            logger.info(f"Successfully reconnected client {client_id}")
            
            # Log success
            config_storage.log_monitoring_event(
                client_id, client['name'], "reconnect_success",
                f"Auto-reconnect completed successfully", 
                f"Client reactivated after DNS IP change"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error during reconnection of client {client_id}: {e}")
            
            # Log failure
            config_storage.log_monitoring_event(
                client_id, client['name'], "reconnect_failed",
                f"Auto-reconnect failed: {str(e)}", 
                f"Error during reconnection process"
            )
            return False
    
    @classmethod
    def _update_reconnection_tracking(cls, client_id: str, success: bool) -> None:
        """
        Update reconnection attempt tracking for a client.
        """
        now = datetime.now()
        
        if client_id not in cls._reconnection_attempts:
            cls._reconnection_attempts[client_id] = {'count': 0, 'last_attempt': now}
        
        attempts = cls._reconnection_attempts[client_id]
        attempts['last_attempt'] = now
        
        if success:
            # Reset attempt counter on success
            attempts['count'] = 0
            attempts['last_success'] = now
            logger.info(f"Reconnection successful for client {client_id} - resetting attempt counter")
        else:
            # Increment attempt counter on failure
            attempts['count'] = attempts.get('count', 0) + 1
            logger.warning(f"Reconnection failed for client {client_id} - attempt {attempts['count']}/{cls.MAX_RECONNECT_ATTEMPTS}")
    
    @classmethod
    def get_reconnection_status(cls) -> Dict[str, Dict]:
        """
        Get current reconnection status for all clients.
        Returns a dictionary with reconnection attempt information.
        """
        status = {}
        now = datetime.now()
        
        for client_id, attempts in cls._reconnection_attempts.items():
            last_attempt = attempts.get('last_attempt')
            last_success = attempts.get('last_success')
            
            status[client_id] = {
                'attempt_count': attempts.get('count', 0),
                'max_attempts': cls.MAX_RECONNECT_ATTEMPTS,
                'last_attempt': last_attempt.isoformat() if last_attempt else None,
                'last_success': last_success.isoformat() if last_success else None,
                'time_since_attempt': (now - last_attempt) if last_attempt else None,
                'time_since_success': (now - last_success) if last_success else None,
                'can_reconnect': cls._should_attempt_reconnection(client_id)
            }
        
        return status
    
    @classmethod
    def clear_reconnection_history(cls, client_id: str) -> None:
        """
        Clear reconnection history for a specific client.
        """
        if client_id in cls._reconnection_attempts:
            del cls._reconnection_attempts[client_id]
            logger.info(f"Cleared reconnection history for client {client_id}")
    
    @classmethod
    def clear_all_reconnection_history(cls) -> None:
        """
        Clear all reconnection history.
        """
        cls._reconnection_attempts.clear()
        logger.info("Cleared all reconnection history") 