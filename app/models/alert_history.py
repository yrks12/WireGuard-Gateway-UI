from datetime import datetime
from app.database import db
import logging

logger = logging.getLogger(__name__)

class AlertHistory(db.Model):
    """Model for storing email alert history."""
    
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(255), nullable=False)
    peer_key = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean, default=True)
    
    @classmethod
    def add_alert(cls, client_name: str, peer_key: str, subject: str, message: str, success: bool = True):
        """Add a new alert to the history with proper session management."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Create a new session for thread safety
                session = db.session
                
                # Check if session is in a bad state and rollback if needed
                if session.is_active and session.in_transaction():
                    try:
                        session.rollback()
                        logger.debug("Rolled back existing transaction before alert insert")
                    except Exception as rollback_err:
                        logger.warning(f"Error during rollback: {rollback_err}")
                
                alert = cls(
                    client_name=client_name,
                    peer_key=peer_key,
                    subject=subject,
                    message=message,
                    success=success
                )
                
                session.add(alert)
                session.commit()
                logger.debug(f"Successfully added alert for {client_name}")
                return alert
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed to add alert for {client_name}: {e}")
                try:
                    db.session.rollback()
                except Exception as rollback_err:
                    logger.warning(f"Error during rollback on attempt {attempt + 1}: {rollback_err}")
                
                if attempt == max_retries - 1:
                    logger.error(f"Failed to add alert after {max_retries} attempts: {e}")
                    return None
                
                # Brief pause before retry
                import time
                time.sleep(0.1)
        
        return None
    
    @classmethod
    def get_recent_alerts(cls, limit: int = 50):
        """Get recent alerts, ordered by most recent first."""
        return cls.query.order_by(cls.sent_at.desc()).limit(limit).all() 