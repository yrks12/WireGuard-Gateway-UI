import subprocess
import logging
from typing import Tuple, Dict, Optional, List
from datetime import datetime, timezone
import time
import re
import ipaddress
import os

logger = logging.getLogger(__name__)

class ConnectivityTestService:
    """Service for testing connectivity to client subnets."""
    
    PING_TIMEOUT = 2  # seconds
    PING_RETRIES = 3
    PING_INTERVAL = 1  # seconds between retries
    
    @staticmethod
    def _get_allowed_ips(interface_name: str) -> List[str]:
        """Get AllowedIPs from WireGuard interface configuration."""
        try:
            # Run wg show to get interface configuration
            result = subprocess.run(
                ['sudo', 'wg', 'show', interface_name, 'allowed-ips'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to get AllowedIPs: {result.stderr}")
                return []
            
            # Parse the output to get AllowedIPs
            allowed_ips = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    # Extract IP address from the line
                    ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', line)
                    if ip_match:
                        allowed_ips.append(ip_match.group(1))
            
            return allowed_ips
            
        except Exception as e:
            logger.error(f"Error getting AllowedIPs: {e}")
            return []
    
    @staticmethod
    def _get_ping_target(subnet: str) -> str:
        """
        Get a ping target IP from a subnet.
        Returns the first usable host IP in the subnet.
        """
        try:
            # Parse the subnet
            network = ipaddress.ip_network(subnet)
            
            # For /32 networks, use the network address itself
            if network.prefixlen == 32:
                return str(network.network_address)
            
            # For other networks, use the first usable host
            return str(list(network.hosts())[0])
            
        except Exception as e:
            logger.error(f"Error getting ping target: {e}")
            return None
    
    @staticmethod
    def test_connectivity(subnet: str) -> Tuple[bool, Optional[Dict]]:
        """
        Test connectivity to a subnet by pinging a target host.
        Returns: (success, result)
        """
        target = ConnectivityTestService._get_ping_target(subnet)
        if not target:
            return False, {
                'success': False,
                'target': subnet,
                'error': 'Could not determine ping target'
            }
        
        for attempt in range(ConnectivityTestService.PING_RETRIES):
            try:
                # Run ping with timeout
                result = subprocess.run(
                    ['sudo', 'ping', '-c', '1', '-W', str(ConnectivityTestService.PING_TIMEOUT), target],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Extract latency from ping output
                    latency_match = re.search(r'time=([0-9.]+) ms', result.stdout)
                    latency = float(latency_match.group(1)) if latency_match else None
                    
                    return True, {
                        'success': True,
                        'target': target,
                        'latency_ms': latency,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                
                # Wait before retry
                if attempt < ConnectivityTestService.PING_RETRIES - 1:
                    time.sleep(ConnectivityTestService.PING_INTERVAL)
                    
            except Exception as e:
                logger.error(f"Ping attempt {attempt + 1} failed: {e}")
                if attempt == ConnectivityTestService.PING_RETRIES - 1:
                    return False, {
                        'success': False,
                        'target': target,
                        'error': str(e),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
        
        return False, {
            'success': False,
            'target': target,
            'error': 'All ping attempts failed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def test_client_connectivity(client_id: str, config_storage) -> Tuple[bool, Optional[Dict]]:
        """
        Test connectivity for a specific client.
        Returns: (success, result)
        """
        client = config_storage.get_client(client_id)
        if not client:
            return False, {
                'success': False,
                'error': 'Client not found',
                'target': 'N/A'
            }
        
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        
        # Get AllowedIPs from WireGuard interface
        allowed_ips = ConnectivityTestService._get_allowed_ips(interface_name)
        if not allowed_ips:
            return False, {
                'success': False,
                'error': 'No AllowedIPs found for client',
                'target': 'N/A'
            }
        
        # Test connectivity to each AllowedIP subnet
        results = []
        for subnet in allowed_ips:
            success, result = ConnectivityTestService.test_connectivity(subnet)
            results.append(result)
            
            # If any subnet is reachable, consider it a success
            if success:
                return True, result
        
        # If all tests failed, return the last result
        last_result = results[-1] if results else {
            'success': False,
            'error': 'No subnets to test',
            'target': 'N/A',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        return False, last_result 