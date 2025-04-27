from datetime import datetime
from app.database import db

class Client(db.Model):
    """WireGuard client model."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    config_path = db.Column(db.String(255), unique=True, nullable=False)
    subnet = db.Column(db.String(18), nullable=False)  # Format: xxx.xxx.xxx.xxx/xx
    public_key = db.Column(db.String(44), unique=True, nullable=False)
    status = db.Column(db.String(20), default='inactive')  # active, inactive
    last_handshake = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Client {self.name}>'

    def to_dict(self):
        """Convert client to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'subnet': self.subnet,
            'status': self.status,
            'last_handshake': self.last_handshake.isoformat() if self.last_handshake else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 