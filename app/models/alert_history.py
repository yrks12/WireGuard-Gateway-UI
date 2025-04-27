from datetime import datetime
from app.database import db

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
        """Add a new alert to the history."""
        alert = cls(
            client_name=client_name,
            peer_key=peer_key,
            subject=subject,
            message=message,
            success=success
        )
        db.session.add(alert)
        db.session.commit()
        return alert
    
    @classmethod
    def get_recent_alerts(cls, limit: int = 50):
        """Get recent alerts, ordered by most recent first."""
        return cls.query.order_by(cls.sent_at.desc()).limit(limit).all() 