import logging
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class RouteCommandGenerator:
    """Service for generating router commands to route traffic through the WireGuard gateway."""
    
    @staticmethod
    def _get_lan_interface() -> Optional[str]:
        """Get the LAN interface name that has the default route."""
        try:
            # Run ip route to get default interface
            result = subprocess.run(
                ['ip', 'route', 'show', 'default'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return None
                
            # Parse the output to get interface name
            # Example output: "default via 192.168.1.1 dev eth0"
            parts = result.stdout.strip().split()
            if len(parts) >= 5 and parts[3] == 'dev':
                return parts[4]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting LAN interface: {e}")
            return None
    
    @staticmethod
    def _get_interface_ip(interface: str) -> Optional[str]:
        """Get the IP address of an interface."""
        try:
            # Run ip addr to get interface IP
            result = subprocess.run(
                ['ip', 'addr', 'show', interface],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return None
                
            # Parse the output to get IP address
            # Example output: "inet 192.168.1.100/24 ..."
            for line in result.stdout.split('\n'):
                if 'inet ' in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        return parts[1].split('/')[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting interface IP: {e}")
            return None
    
    @staticmethod
    def generate_route_command(client_subnet: str) -> Tuple[bool, Optional[str]]:
        """
        Generate the route command for a client's subnet.
        Returns: (success, command)
        """
        try:
            # Get LAN interface
            interface = RouteCommandGenerator._get_lan_interface()
            if not interface:
                return False, "Could not determine LAN interface"
            
            # Get gateway IP
            gateway_ip = RouteCommandGenerator._get_interface_ip(interface)
            if not gateway_ip:
                return False, "Could not determine gateway IP"
            
            # Generate command
            command = f"ip route add {client_subnet} via {gateway_ip} dev {interface}"
            return True, command
            
        except Exception as e:
            logger.error(f"Error generating route command: {e}")
            return False, str(e) 