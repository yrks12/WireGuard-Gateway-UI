import logging
import subprocess
import psutil
from typing import Dict, Optional, List
from datetime import datetime
import os
from app.services.ip_forwarding import IPForwardingService

logger = logging.getLogger(__name__)

class StatusPoller:
    """Service for collecting system and WireGuard status metrics."""
    
    @staticmethod
    def get_system_metrics() -> Dict:
        """Get system metrics (CPU, RAM, etc.)."""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'ip_forwarding': IPForwardingService.check_status(),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def get_wireguard_status(interface: str) -> Dict:
        """Get WireGuard interface status including last handshake."""
        try:
            # Run wg show to get interface status
            result = subprocess.run(
                ['sudo', 'wg', 'show', interface],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return {
                    'error': result.stderr,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Parse the output
            status = {
                'interface': interface,
                'peers': [],
                'timestamp': datetime.utcnow().isoformat()
            }
            
            current_peer = None
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('peer:'):
                    if current_peer:
                        status['peers'].append(current_peer)
                    current_peer = {'public_key': line.split(':')[1].strip()}
                elif current_peer and ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    
                    # Convert handshake time to ISO format
                    if key == 'latest_handshake':
                        try:
                            value = datetime.fromtimestamp(int(value)).isoformat()
                        except (ValueError, TypeError):
                            pass
                    
                    current_peer[key] = value
            
            if current_peer:
                status['peers'].append(current_peer)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting WireGuard status: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def get_all_status(client_id: str, config_storage) -> Dict:
        """Get combined status for a client including system metrics and WireGuard status."""
        try:
            client = config_storage.get_client(client_id)
            if not client:
                return {
                    'error': 'Client not found',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Get interface name from config path
            interface = os.path.splitext(os.path.basename(client['config_path']))[0]
            
            # Get all status information
            system_metrics = StatusPoller.get_system_metrics()
            wg_status = StatusPoller.get_wireguard_status(interface)
            
            # Combine results
            status = {
                'system': system_metrics,
                'wireguard': wg_status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting all status: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            } 