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
    # Consider a peer disconnected if no handshake for 30 minutes (prevent false positives)
    DISCONNECT_THRESHOLD = timedelta(minutes=30)
    
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
                # Check if interface doesn't exist (common for inactive interfaces)
                if "No such device" in result.stderr:
                    logger.debug(f"Interface {interface} not found (inactive): {result.stderr}")
                else:
                    logger.error(f"Failed to check interface {interface}: {result.stderr}")
                return {}
            
            # Parse output
            peers = {}
            current_peer = None
            
            # Track which peers have handshake data  
            peers_with_handshakes = set()
            
            for line in result.stdout.splitlines():
                if line.startswith('peer: '):
                    current_peer = line.split(': ')[1]
                    # Default to True - interface is up and peer is configured
                    peers[current_peer] = True
                    logger.debug(f"Found peer {current_peer[:8]}..., defaulting to connected=True")
                elif line.startswith('  latest handshake:') and current_peer:
                    handshake_str = line.split(': ')[1]
                    if handshake_str != '0':
                        try:
                            # Handle "Now" case
                            if handshake_str.strip() == "Now":
                                handshake_time = datetime.now()
                                cls._last_handshakes[current_peer] = handshake_time
                                peers[current_peer] = True
                                logger.debug(f"Peer {current_peer[:8]}... handshake is 'Now', keeping connected=True")
                                continue
                            
                            # Calculate the actual timestamp by subtracting the time ago from current time
                            total_seconds = 0
                            
                            # Handle combined formats like "1 minute, 45 seconds ago"
                            if ',' in handshake_str:
                                parts = handshake_str.split(',')
                                for part in parts:
                                    part = part.strip()
                                    if 'minute' in part:
                                        minutes = int(part.split()[0])
                                        total_seconds += minutes * 60
                                    elif 'second' in part:
                                        seconds = int(part.split()[0])
                                        total_seconds += seconds
                            else:
                                # Handle single unit formats
                                if 'seconds ago' in handshake_str:
                                    total_seconds = int(handshake_str.split()[0])
                                elif 'minutes ago' in handshake_str:
                                    total_seconds = int(handshake_str.split()[0]) * 60
                                elif 'hours ago' in handshake_str:
                                    total_seconds = int(handshake_str.split()[0]) * 3600
                                elif 'days ago' in handshake_str:
                                    total_seconds = int(handshake_str.split()[0]) * 86400
                            
                            handshake_time = datetime.now() - timedelta(seconds=total_seconds)
                            cls._last_handshakes[current_peer] = handshake_time
                            
                            # Check if handshake is recent enough to consider connected
                            time_since_handshake = datetime.now() - handshake_time
                            if time_since_handshake <= cls.DISCONNECT_THRESHOLD:
                                peers[current_peer] = True
                                logger.debug(f"Peer {current_peer[:8]}... within threshold ({time_since_handshake}), keeping connected=True")
                            else:
                                peers[current_peer] = False
                                logger.warning(f"Peer {current_peer[:8]}... exceeded disconnect threshold: {time_since_handshake} > {cls.DISCONNECT_THRESHOLD}, setting connected=False")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Failed to parse handshake time for {current_peer[:8]}: {handshake_str}")
                            # Keep peer as connected - parsing failure doesn't mean disconnection
            
            # CRITICAL FIX: If no handshake line was found for a peer, keep it as connected
            # Missing handshake line means no recent activity, not disconnection
            
            return peers
            
        except Exception as e:
            logger.error(f"Error checking interface {interface}: {e}")
            return {}
    
    @classmethod
    def check_and_alert(cls, interface: str, client_name: str, client_id: str = None, config_storage=None) -> None:
        """
        Check interface status and send alerts if peers are disconnected.
        """
        peers = cls.check_interface(interface)
        now = datetime.now()
        
        for peer, is_connected in peers.items():
            logger.warning(f"Alert check: peer {peer[:8]}... is_connected={is_connected}")
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
                            # Log monitoring event
                            if config_storage and client_id:
                                config_storage.log_monitoring_event(
                                    client_id, client_name, "disconnect_alert", 
                                    f"Client disconnected - alert sent", 
                                    f"Peer: {peer[:8]}..."
                                )
                        else:
                            logger.error(f"Failed to send disconnect alert for {client_name}")
                            # Log monitoring event
                            if config_storage and client_id:
                                config_storage.log_monitoring_event(
                                    client_id, client_name, "disconnect_alert_failed", 
                                    f"Client disconnected - alert failed", 
                                    f"Peer: {peer[:8]}..."
                                )
                    except Exception as e:
                        logger.error(f"Error sending alert: {e}")
                        # Log monitoring event
                        if config_storage and client_id:
                            config_storage.log_monitoring_event(
                                client_id, client_name, "alert_error", 
                                f"Error sending disconnect alert: {str(e)}", 
                                f"Peer: {peer[:8]}..."
                            )
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