import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import shutil
from pathlib import Path
import pwd
import grp

class ConfigStorageService:
    """Service for managing WireGuard config storage and metadata."""
    
    def __init__(self, storage_dir: str, db_path: str):
        self.storage_dir = storage_dir
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize the SQLite database with required tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    config_path TEXT NOT NULL,
                    subnet TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'inactive',
                    last_handshake TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    latency_ms INTEGER,
                    success BOOLEAN,
                    target TEXT,
                    error TEXT,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)
    
    def store_config(self, config_content: str, subnet: str, public_key: str, original_filename: str = None) -> Tuple[str, Dict]:
        """
        Store a WireGuard config and its metadata.
        Args:
            config_content: The content of the WireGuard config file
            subnet: The subnet for this client
            public_key: The client's public key
            original_filename: The original filename of the uploaded config (optional)
        Returns: (client_id, metadata)
        """
        # Generate unique client ID
        client_id = str(uuid.uuid4())
        
        # Create client name from original filename or generate one
        if original_filename:
            # Remove .conf extension if present
            base_name = os.path.splitext(original_filename)[0]
            client_name = f"{base_name}_{client_id[:8]}"
        else:
            client_name = f"client_{client_id[:8]}"
        
        # Ensure storage directory exists
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Create config file paths
        config_filename = f"{client_name}.conf"
        config_path = os.path.join(self.storage_dir, config_filename)
        wg_config_path = os.path.join('/etc/wireguard', config_filename)
        
        # Write config file to both locations
        for path in [config_path, wg_config_path]:
            with open(path, 'w') as f:
                f.write(config_content)
            
            # Set proper permissions and ownership
            os.chmod(path, 0o640)  # Readable by owner and group, writable by owner only
            # Get wireguard user and group IDs
            wireguard_uid = pwd.getpwnam('wireguard').pw_uid
            wireguard_gid = grp.getgrnam('wireguard').gr_gid
            os.chown(path, wireguard_uid, wireguard_gid)  # wireguard:wireguard ownership
        
        # Store metadata in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO clients (id, name, config_path, subnet, public_key, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (client_id, client_name, wg_config_path, subnet, public_key, 'inactive'))
            
            # Get the stored metadata
            cursor = conn.execute("""
                SELECT id, name, config_path, subnet, public_key, status, last_handshake, created_at, updated_at
                FROM clients WHERE id = ?
            """, (client_id,))
            
            row = cursor.fetchone()
            metadata = {
                'id': row[0],
                'name': row[1],
                'config_path': row[2],
                'subnet': row[3],
                'public_key': row[4],
                'status': row[5],
                'last_handshake': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        
        # Register hostname for DNS monitoring if present
        self._register_hostname_for_monitoring(client_id, config_content)
        
        return client_id, metadata
    
    def _register_hostname_for_monitoring(self, client_id: str, config_content: str) -> None:
        """
        Register a client's hostname for DNS monitoring if present in config.
        """
        try:
            from app.services.dns_resolver import DNSResolver
            
            # Extract hostname from config
            hostname = DNSResolver.extract_hostname_from_config(config_content)
            if hostname:
                # Get client name from database
                client = self.get_client(client_id)
                client_name = client.get('name', 'Unknown') if client else 'Unknown'
                
                DNSResolver.register_client_hostname(client_id, hostname, client_name)
        except Exception as e:
            # Log error but don't fail the config storage
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to register hostname for client {client_id}: {e}")
    
    def get_client(self, client_id: str) -> Optional[Dict]:
        """Retrieve client metadata by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, name, config_path, subnet, public_key, status, last_handshake, created_at, updated_at
                FROM clients WHERE id = ?
            """, (client_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return {
                'id': row[0],
                'name': row[1],
                'config_path': row[2],
                'subnet': row[3],
                'public_key': row[4],
                'status': row[5],
                'last_handshake': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
    
    def list_clients(self) -> List[Dict]:
        """List all stored clients."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, name, config_path, subnet, public_key, status, last_handshake, created_at, updated_at
                FROM clients
            """)
            
            return [{
                'id': row[0],
                'name': row[1],
                'config_path': row[2],
                'subnet': row[3],
                'public_key': row[4],
                'status': row[5],
                'last_handshake': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            } for row in cursor.fetchall()]
    
    def update_client_status(self, client_id: str, status: str, last_handshake: Optional[datetime] = None):
        """Update client status and last handshake time."""
        with sqlite3.connect(self.db_path) as conn:
            if last_handshake:
                conn.execute("""
                    UPDATE clients 
                    SET status = ?, last_handshake = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, last_handshake, client_id))
            else:
                conn.execute("""
                    UPDATE clients 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, client_id))
    
    def add_test_result(self, client_id: str, latency_ms: Optional[int], success: bool, target: str = 'N/A', error: Optional[str] = None):
        """Add a connectivity test result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO test_history (client_id, latency_ms, success, target, error)
                VALUES (?, ?, ?, ?, ?)
            """, (client_id, latency_ms, success, target, error))
    
    def get_test_history(self, client_id: str, limit: int = 5) -> List[Dict]:
        """Get recent test history for a client."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, latency_ms, success, target, error
                FROM test_history
                WHERE client_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (client_id, limit))
            
            return [{
                'timestamp': row[0],
                'latency_ms': row[1],
                'success': row[2],
                'target': row[3],
                'error': row[4]
            } for row in cursor.fetchall()]
    
    def delete_client(self, client_id: str) -> bool:
        """Delete a client and its config files."""
        client = self.get_client(client_id)
        if not client:
            return False
            
        # Delete config files from both locations
        config_filename = os.path.basename(client['config_path'])
        app_config_path = os.path.join(self.storage_dir, config_filename)
        wg_config_path = os.path.join('/etc/wireguard', config_filename)
        
        for path in [app_config_path, wg_config_path]:
            try:
                os.remove(path)
            except OSError:
                pass
            
        # Unregister hostname from DNS monitoring
        try:
            from app.services.dns_resolver import DNSResolver
            DNSResolver.unregister_client_hostname(client_id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to unregister hostname for client {client_id}: {e}")
            
        # Delete from database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            conn.execute("DELETE FROM test_history WHERE client_id = ?", (client_id,))
            
        return True 