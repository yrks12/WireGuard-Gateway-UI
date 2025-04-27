from datetime import datetime
from app.database import db

class EmailSettings(db.Model):
    """Model for storing email alert settings."""
    
    id = db.Column(db.Integer, primary_key=True)
    smtp_host = db.Column(db.String(255), nullable=False)
    smtp_port = db.Column(db.Integer, nullable=False)
    smtp_username = db.Column(db.String(255), nullable=False)
    smtp_password = db.Column(db.String(255), nullable=False)
    smtp_from = db.Column(db.String(255), nullable=False)
    smtp_use_tls = db.Column(db.Boolean, default=True)
    alert_recipients = db.Column(db.String(1000), nullable=False)  # Comma-separated emails
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_settings(cls):
        """Get the current email settings."""
        return cls.query.first()
    
    @classmethod
    def update_settings(cls, **kwargs):
        """Update email settings."""
        settings = cls.get_settings()
        if not settings:
            settings = cls()
        
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        db.session.add(settings)
        db.session.commit()
        return settings
    
    def get_recipients(self) -> list:
        """Get list of alert recipients."""
        return [email.strip() for email in self.alert_recipients.split(',') if email.strip()] 