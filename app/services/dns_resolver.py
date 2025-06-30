import socket
import logging
import re
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import threading
import time

logger = logging.getLogger(__name__)

class DNSResolver:
    """Service for tracking DNS resolution and detecting IP changes for DDNS hostnames."""
    
    # Store resolved IPs for each hostname
    _resolved_ips: Dict[str, str] = {}
    # Store last check times to avoid excessive DNS queries
    _last_checks: Dict[str, datetime] = {}
    # Store client associations (hostname -> client_id)
    _client_hostnames: Dict[str, str] = {}
    # Store client names for display (client_id -> client_name)
    _client_names: Dict[str, str] = {}
    # DNS check interval (5 minutes)
    DNS_CHECK_INTERVAL = timedelta(minutes=5)
    # Callback for handling DNS changes
    _dns_change_callback = None
    
    @classmethod
    def extract_hostname_from_config(cls, config_content: str) -> Optional[str]:
        """
        Extract the endpoint hostname from a WireGuard config.
        Returns the hostname if found, None otherwise.
        """
        try:
            # Look for Endpoint line in config
            endpoint_match = re.search(r'Endpoint\s*=\s*([^:]+):(\d+)', config_content)
            if endpoint_match:
                hostname = endpoint_match.group(1).strip()
                # Skip if it's already an IP address
                if not cls._is_ip_address(hostname):
                    return hostname
            return None
        except Exception as e:
            logger.error(f"Error extracting hostname from config: {e}")
            return None
    
    @staticmethod
    def _is_ip_address(hostname: str) -> bool:
        """Check if a hostname is actually an IP address."""
        try:
            socket.inet_aton(hostname)
            return True
        except socket.error:
            return False
    
    @classmethod
    def resolve_hostname(cls, hostname: str) -> Optional[str]:
        """
        Resolve a hostname to an IP address.
        Returns the IP address if successful, None otherwise.
        """
        try:
            # Use socket to resolve hostname
            ip_address = socket.gethostbyname(hostname)
            logger.debug(f"Resolved {hostname} to {ip_address}")
            return ip_address
        except socket.gaierror as e:
            logger.error(f"Failed to resolve hostname {hostname}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error resolving {hostname}: {e}")
            return None
    
    @classmethod
    def register_client_hostname(cls, client_id: str, hostname: str, client_name: str = None) -> None:
        """
        Register a client's hostname for monitoring.
        """
        cls._client_hostnames[hostname] = client_id
        if client_name:
            cls._client_names[client_id] = client_name
        logger.info(f"Registered hostname {hostname} for client {client_id}")
    
    @classmethod
    def unregister_client_hostname(cls, client_id: str) -> None:
        """
        Unregister a client's hostname from monitoring.
        """
        hostnames_to_remove = []
        for hostname, registered_client_id in cls._client_hostnames.items():
            if registered_client_id == client_id:
                hostnames_to_remove.append(hostname)
        
        for hostname in hostnames_to_remove:
            del cls._client_hostnames[hostname]
            if hostname in cls._resolved_ips:
                del cls._resolved_ips[hostname]
            if hostname in cls._last_checks:
                del cls._last_checks[hostname]
        
        # Remove client name
        if client_id in cls._client_names:
            del cls._client_names[client_id]
        
        if hostnames_to_remove:
            logger.info(f"Unregistered hostnames {hostnames_to_remove} for client {client_id}")
    
    @classmethod
    def set_dns_change_callback(cls, callback) -> None:
        """
        Set a callback function to be called when DNS changes are detected.
        The callback should accept a list of change dictionaries.
        """
        cls._dns_change_callback = callback
        logger.info("DNS change callback registered")
    
    @classmethod
    def check_hostname_changes(cls) -> List[Dict]:
        """
        Check all registered hostnames for IP changes.
        Returns a list of changes detected.
        """
        changes = []
        now = datetime.now()
        
        for hostname, client_id in cls._client_hostnames.items():
            # Check if enough time has passed since last check
            last_check = cls._last_checks.get(hostname)
            if last_check and (now - last_check) < cls.DNS_CHECK_INTERVAL:
                continue
            
            # Resolve current IP
            current_ip = cls.resolve_hostname(hostname)
            if not current_ip:
                continue
            
            # Update last check time
            cls._last_checks[hostname] = now
            
            # Check if IP has changed
            previous_ip = cls._resolved_ips.get(hostname)
            if previous_ip and previous_ip != current_ip:
                change_info = {
                    'client_id': client_id,
                    'hostname': hostname,
                    'previous_ip': previous_ip,
                    'current_ip': current_ip,
                    'timestamp': now
                }
                changes.append(change_info)
                logger.info(f"IP change detected for {hostname}: {previous_ip} -> {current_ip}")
            
            # Update stored IP
            cls._resolved_ips[hostname] = current_ip
        
        return changes
    
    @classmethod
    def get_hostname_status(cls) -> Dict[str, Dict]:
        """
        Get current status of all monitored hostnames.
        Returns a dictionary with hostname status information.
        """
        status = {}
        now = datetime.now()
        
        for hostname, client_id in cls._client_hostnames.items():
            last_check = cls._last_checks.get(hostname)
            resolved_ip = cls._resolved_ips.get(hostname)
            client_name = cls._client_names.get(client_id, 'Unknown')
            
            status[hostname] = {
                'client_id': client_id,
                'client_name': client_name,
                'resolved_ip': resolved_ip,
                'last_check': last_check.isoformat() if last_check else None,
                'time_since_check': str(now - last_check) if last_check else None
            }
        
        return status
    
    @classmethod
    def start_monitoring(cls) -> None:
        """
        Start the DNS monitoring thread.
        """
        def monitor_dns():
            """Background thread for DNS monitoring."""
            logger.info("Starting DNS monitoring thread")
            while True:
                try:
                    changes = cls.check_hostname_changes()
                    if changes:
                        # Trigger reconnection for changed hostnames
                        cls._trigger_reconnections(changes)
                    
                    # Sleep for 1 minute before next check
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"Error in DNS monitoring thread: {e}")
                    time.sleep(60)  # Continue monitoring even if there's an error
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_dns, daemon=True)
        monitor_thread.start()
        logger.info("DNS monitoring thread started")
    
    @classmethod
    def _trigger_reconnections(cls, changes: List[Dict]) -> None:
        """
        Trigger reconnections for clients with IP changes.
        """
        if cls._dns_change_callback:
            try:
                cls._dns_change_callback(changes)
                logger.info(f"Triggered reconnection for {len(changes)} DNS changes")
            except Exception as e:
                logger.error(f"Error in DNS change callback: {e}")
        else:
            # Fallback: just log the changes
            for change in changes:
                logger.info(f"IP change detected - no callback registered for client {change['client_id']}") 