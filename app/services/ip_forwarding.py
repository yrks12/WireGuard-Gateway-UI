import subprocess
import os
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class IPForwardingService:
    """Service for managing IP forwarding settings."""
    
    SYSCTL_CONF = '/etc/sysctl.conf'
    IP_FORWARD_FILE = '/proc/sys/net/ipv4/ip_forward'
    IP_FORWARD_KEY = 'net.ipv4.ip_forward'
    
    @staticmethod
    def check_status() -> bool:
        """Check if IP forwarding is currently enabled."""
        try:
            with open(IPForwardingService.IP_FORWARD_FILE, 'r') as f:
                return f.read().strip() == '1'
        except Exception as e:
            logger.error(f"Failed to check IP forwarding status: {e}")
            return False
    
    @staticmethod
    def enable_temporary() -> Tuple[bool, Optional[str]]:
        """Enable IP forwarding temporarily (until reboot)."""
        try:
            result = subprocess.run(
                ['sudo', 'sysctl', '-w', f'{IPForwardingService.IP_FORWARD_KEY}=1'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return False, f"Failed to enable IP forwarding: {result.stderr}"
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def enable_permanent() -> Tuple[bool, Optional[str]]:
        """Enable IP forwarding permanently (survives reboot)."""
        try:
            # First, check if the setting already exists
            setting_exists = False
            if os.path.exists(IPForwardingService.SYSCTL_CONF):
                with open(IPForwardingService.SYSCTL_CONF, 'r') as f:
                    content = f.read()
                    setting_exists = IPForwardingService.IP_FORWARD_KEY in content
            
            if not setting_exists:
                # Create the setting content
                setting = f"\n# Enable IP forwarding for WireGuard\n{IPForwardingService.IP_FORWARD_KEY} = 1\n"
                
                # Use echo and sudo tee to append to sysctl.conf
                result = subprocess.run(
                    ['sudo', 'tee', '-a', IPForwardingService.SYSCTL_CONF],
                    input=setting,
                    text=True,
                    capture_output=True
                )
                if result.returncode != 0:
                    return False, f"Failed to update sysctl.conf: {result.stderr}"
            
            # Apply the changes
            result = subprocess.run(
                ['sudo', 'sysctl', '-p'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return False, f"Failed to apply sysctl changes: {result.stderr}"
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def disable_temporary() -> Tuple[bool, Optional[str]]:
        """Disable IP forwarding temporarily (until reboot)."""
        try:
            result = subprocess.run(
                ['sudo', 'sysctl', '-w', f'{IPForwardingService.IP_FORWARD_KEY}=0'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return False, f"Failed to disable IP forwarding: {result.stderr}"
            return True, None
        except Exception as e:
            return False, str(e) 