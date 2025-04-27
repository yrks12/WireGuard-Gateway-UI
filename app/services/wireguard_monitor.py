import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.services.email_service import EmailService
from app.models.alert_history import AlertHistory
from flask import current_app

logger = logging.getLogger(__name__)

class WireGuardMonitor:
    """Service for monitoring WireGuard interfaces and connections."""
    
    # Store last handshake times for each peer
    _last_handshakes: Dict[str, datetime] = {}
    # Store last alert times to prevent spam
    _last_alerts: Dict[str, datetime] = {}
    # Alert cooldown period (1 hour)
    ALERT_COOLDOWN = timedelta(hours=1)
    # Consider a peer disconnected if no handshake for 3 minutes
    DISCONNECT_THRESHOLD = timedelta(minutes=3)
    
    @classmethod
    def check_interface(cls, interface: str) -> Dict[str, bool]:
        """
        Check the status of a WireGuard interface and its peers.
        Returns a dictionary mapping peer public keys to their connection status.
        """
        try:
            # Run wg show command
            result = subprocess.run(
                ['sudo', 'wg', 'show', interface],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to check interface {interface}: {result.stderr}")
                return {}
            
            # Parse output
            peers = {}
            current_peer = None
            
            for line in result.stdout.splitlines():
                if line.startswith('peer: '):
                    current_peer = line.split(': ')[1]
                    peers[current_peer] = False
                elif line.startswith('  latest handshake:') and current_peer:
                    handshake_str = line.split(': ')[1]
                    if handshake_str != '0':
                        try:
                            # Parse handshake time
                            handshake_time = datetime.strptime(handshake_str, '%Y-%m-%d %H:%M:%S')
                            peers[current_peer] = True
                            cls._last_handshakes[current_peer] = handshake_time
                        except ValueError:
                            logger.error(f"Failed to parse handshake time: {handshake_str}")
            
            return peers
            
        except Exception as e:
            logger.error(f"Error checking interface {interface}: {e}")
            return {}
    
    @classmethod
    def check_and_alert(cls, interface: str, client_name: str) -> None:
        """
        Check interface status and send alerts if peers are disconnected.
        """
        peers = cls.check_interface(interface)
        now = datetime.now()
        
        for peer, is_connected in peers.items():
            if not is_connected:
                # Check if we should send an alert
                last_alert = cls._last_alerts.get(peer)
                if not last_alert or (now - last_alert) > cls.ALERT_COOLDOWN:
                    # Send alert
                    subject = f"Client Disconnected: {client_name}"
                    message = f"The client '{client_name}' (peer: {peer[:8]}...) has disconnected from the VPN."
                    
                    try:
                        success = EmailService.send_alert(subject, message)
                        # Log alert to database
                        AlertHistory.add_alert(
                            client_name=client_name,
                            peer_key=peer,
                            subject=subject,
                            message=message,
                            success=success
                        )
                        
                        if success:
                            cls._last_alerts[peer] = now
                            logger.info(f"Sent disconnect alert for {client_name}")
                        else:
                            logger.error(f"Failed to send disconnect alert for {client_name}")
                    except Exception as e:
                        logger.error(f"Error sending alert: {e}")
                        # Log failed alert
                        AlertHistory.add_alert(
                            client_name=client_name,
                            peer_key=peer,
                            subject=subject,
                            message=message,
                            success=False
                        )
    
    @classmethod
    def is_peer_connected(cls, peer_key: str) -> bool:
        """
        Check if a peer is connected based on last handshake time.
        """
        last_handshake = cls._last_handshakes.get(peer_key)
        if not last_handshake:
            return False
            
        return (datetime.now() - last_handshake) < cls.DISCONNECT_THRESHOLD
    
    @classmethod
    def get_connection_status(cls) -> Dict[str, Dict]:
        """
        Get current connection status for all peers.
        Returns a dictionary mapping peer keys to their status information.
        """
        status = {}
        now = datetime.now()
        
        for peer_key, last_handshake in cls._last_handshakes.items():
            is_connected = (now - last_handshake) < cls.DISCONNECT_THRESHOLD
            last_alert = cls._last_alerts.get(peer_key)
            
            status[peer_key] = {
                'connected': is_connected,
                'last_handshake': last_handshake,
                'last_alert': last_alert,
                'time_since_handshake': now - last_handshake
            }
        
        return status 