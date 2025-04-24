import os
import subprocess
import re
from typing import Dict, Optional, Tuple
from flask import current_app

class WireGuardService:
    """Service for managing WireGuard VPN operations."""
    
    @staticmethod
    def validate_config(config_content: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate WireGuard config file content.
        Returns: (is_valid, error_message, config_data)
        """
        if '[Interface]' not in config_content:
            return False, "Missing [Interface] section", None
        
        if '[Peer]' not in config_content:
            return False, "Missing [Peer] section", None
            
        config_data = {
            'public_key': None,
            'allowed_ips': None
        }
        
        # Extract PublicKey from [Peer] section
        public_key_match = re.search(r'PublicKey\s*=\s*([a-zA-Z0-9+/]{43}=)', config_content)
        if not public_key_match:
            return False, "Invalid or missing PublicKey in [Peer] section", None
        config_data['public_key'] = public_key_match.group(1)
        
        # Extract AllowedIPs
        allowed_ips_match = re.search(r'AllowedIPs\s*=\s*([0-9./,\s]+)', config_content)
        if not allowed_ips_match:
            return False, "Missing AllowedIPs in config", None
        
        allowed_ips = allowed_ips_match.group(1).strip()
        if allowed_ips == '0.0.0.0/0':
            return False, "AllowedIPs cannot be 0.0.0.0/0. Please specify a subnet.", None
        
        config_data['allowed_ips'] = allowed_ips
        return True, None, config_data

    @staticmethod
    def activate_client(config_path: str) -> Tuple[bool, Optional[str]]:
        """
        Activate a WireGuard client using wg-quick.
        Returns: (success, error_message)
        """
        try:
            result = subprocess.run(['sudo', 'wg-quick', 'up', config_path],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to activate client: {result.stderr}"
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def deactivate_client(config_path: str) -> Tuple[bool, Optional[str]]:
        """
        Deactivate a WireGuard client using wg-quick.
        Returns: (success, error_message)
        """
        try:
            result = subprocess.run(['sudo', 'wg-quick', 'down', config_path],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to deactivate client: {result.stderr}"
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_client_status(interface_name: str) -> Dict:
        """
        Get client connection status using wg show.
        Returns: Dictionary with status information
        """
        try:
            result = subprocess.run(['sudo', 'wg', 'show', interface_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return {'error': result.stderr}
            
            # Parse wg show output
            output = result.stdout
            status = {
                'interface': interface_name,
                'connected': 'peer' in output.lower(),
                'last_handshake': None
            }
            
            # Extract last handshake time if available
            handshake_match = re.search(r'latest handshake: (.+)', output)
            if handshake_match:
                status['last_handshake'] = handshake_match.group(1)
                
            return status
        except Exception as e:
            return {'error': str(e)} 