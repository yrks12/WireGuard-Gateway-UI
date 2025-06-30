import subprocess
import re
import logging
from typing import Tuple, Optional, List, Dict
import netifaces

logger = logging.getLogger(__name__)

class IptablesManager:
    """Service for managing iptables rules for WireGuard clients."""
    
    @staticmethod
    def _get_lan_interface() -> Optional[str]:
        """Get the LAN interface name (the one with the default route)."""
        try:
            # Get the default route
            result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                 capture_output=True, text=True)
            if result.returncode != 0:
                return None
            
            # Extract the interface name from the default route
            match = re.search(r'dev\s+(\w+)', result.stdout)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error getting LAN interface: {e}")
            return None

    @staticmethod
    def _get_interface_ip(interface: str) -> Optional[str]:
        """Get the IP address of an interface."""
        try:
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                return addrs[netifaces.AF_INET][0]['addr']
            return None
        except Exception as e:
            logger.error(f"Error getting interface IP: {e}")
            return None

    @staticmethod
    def setup_forwarding(client_interface: str, client_subnet: str) -> Tuple[bool, Optional[str]]:
        """
        Set up iptables rules for a WireGuard client.
        Args:
            client_interface: WireGuard interface name
            client_subnet: Client's allowed subnet (e.g., '192.168.1.0/24')
        Returns: (success, error_message)
        """
        try:
            # Get LAN interface
            lan_interface = IptablesManager._get_lan_interface()
            if not lan_interface:
                return False, "Could not determine LAN interface"

            # Enable IP forwarding
            result = subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=1'],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to enable IP forwarding: {result.stderr}"

            # Add NAT rules for WireGuard interface (like original: -o SITEB -j MASQUERADE)
            nat_cmds = [
                ['sudo', 'iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', client_interface, '-j', 'MASQUERADE']
            ]
            
            # Add forwarding rules for WireGuard interface (like original setup)
            forward_cmds = [
                ['sudo', 'iptables', '-A', 'FORWARD', '-i', lan_interface, '-o', client_interface, '-j', 'ACCEPT'],
                ['sudo', 'iptables', '-A', 'FORWARD', '-i', client_interface, '-o', lan_interface, '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT']
            ]

            # Execute all commands
            for cmd in nat_cmds + forward_cmds:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    # Try to clean up any rules that were added
                    IptablesManager.cleanup_forwarding(client_interface, client_subnet)
                    return False, f"Failed to add iptables rule: {result.stderr}"

            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def cleanup_forwarding(client_interface: str, client_subnet: str) -> Tuple[bool, Optional[str]]:
        """
        Remove iptables rules for a WireGuard client.
        Args:
            client_interface: WireGuard interface name
            client_subnet: Client's allowed subnet (e.g., '192.168.1.0/24')
        Returns: (success, error_message)
        """
        try:
            # Get LAN interface
            lan_interface = IptablesManager._get_lan_interface()
            if not lan_interface:
                return False, "Could not determine LAN interface"

            # Remove NAT rules for WireGuard interface
            nat_cmds = [
                ['sudo', 'iptables', '-t', 'nat', '-D', 'POSTROUTING', '-o', client_interface, '-j', 'MASQUERADE']
            ]
            
            # Remove forwarding rules for WireGuard interface
            forward_cmds = [
                ['sudo', 'iptables', '-D', 'FORWARD', '-i', lan_interface, '-o', client_interface, '-j', 'ACCEPT'],
                ['sudo', 'iptables', '-D', 'FORWARD', '-i', client_interface, '-o', lan_interface, '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT']
            ]

            # Execute all commands
            for cmd in nat_cmds + forward_cmds:
                result = subprocess.run(cmd, capture_output=True, text=True)
                # Don't fail if rule doesn't exist
                if result.returncode != 0 and "No chain/target/match" not in result.stderr:
                    return False, f"Failed to remove iptables rule: {result.stderr}"

            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_router_command(client_interface: str, client_subnet: str) -> Optional[str]:
        """
        Generate the router command for a client.
        Returns: The command to run on the router, or None if interface IP couldn't be determined
        """
        try:
            # Get LAN interface IP
            lan_interface = IptablesManager._get_lan_interface()
            if not lan_interface:
                return None
            
            lan_ip = IptablesManager._get_interface_ip(lan_interface)
            if not lan_ip:
                return None

            return f"ip route add {client_subnet} via {lan_ip} dev {lan_interface}"
        except Exception as e:
            logger.error(f"Error generating router command: {e}")
            return None

    @staticmethod
    def get_forwarding_rules(client_interface: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Get the current iptables rules for a client.
        Returns: (success, rules, error_message)
        """
        try:
            # Get NAT rules
            nat_result = subprocess.run(
                ['sudo', 'iptables', '-t', 'nat', '-L', 'POSTROUTING', '-v', '-n'],
                capture_output=True, text=True
            )
            
            # Get FORWARD rules
            forward_result = subprocess.run(
                ['sudo', 'iptables', '-L', 'FORWARD', '-v', '-n'],
                capture_output=True, text=True
            )
            
            if nat_result.returncode != 0 or forward_result.returncode != 0:
                return False, None, "Failed to get iptables rules"
            
            # Parse rules
            rules = {
                'nat': [],
                'forward': []
            }
            
            # Parse NAT rules
            for line in nat_result.stdout.split('\n'):
                if client_interface in line:
                    rules['nat'].append(line.strip())
            
            # Parse FORWARD rules
            for line in forward_result.stdout.split('\n'):
                if client_interface in line:
                    rules['forward'].append(line.strip())
            
            return True, rules, None
        except Exception as e:
            return False, None, str(e) 