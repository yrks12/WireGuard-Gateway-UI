import uuid
import json
import re
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

class PendingConfigsService:
    """Service for managing WireGuard configs pending subnet input."""
    
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def _get_config_path(self, config_id: str) -> str:
        """Get the file path for a pending config."""
        return os.path.join(self.storage_dir, f"{config_id}.json")
    
    def store_pending_config(self, config_content: str) -> str:
        """
        Store a new config that requires subnet input.
        Returns the config ID.
        """
        config_id = str(uuid.uuid4())
        config_path = self._get_config_path(config_id)
        
        # Calculate expiration time (24 hours from now)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Store config with metadata
        config_data = {
            'content': config_content,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': expires_at.isoformat()
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
            
        return config_id
    
    def get_pending_config(self, config_id: str) -> Optional[Dict]:
        """Get a pending config by ID."""
        config_path = self._get_config_path(config_id)
        if not os.path.exists(config_path):
            return None

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # Check if expired
            if 'expires_at' not in config_data:
                # If no expiration set, set it to 24 hours from now
                config_data['expires_at'] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                with open(config_path, 'w') as f:
                    json.dump(config_data, f)
            else:
                expires_at = datetime.fromisoformat(config_data['expires_at'])
                if datetime.utcnow() > expires_at:
                    self.delete_pending_config(config_id)
                    return None

            return config_data
        except Exception as e:
            logger.error(f"Error reading pending config {config_id}: {str(e)}")
            return None
    
    def update_config_with_subnet(self, config_id: str, subnet: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Update a pending config with a new subnet.
        Returns: (success, error_message, updated_config)
        """
        config_data = self.get_pending_config(config_id)
        if not config_data:
            return False, "Config not found or expired", None
        
        # Update the config content with new subnet
        content = config_data['content']
        updated_content = re.sub(
            r'AllowedIPs\s*=\s*[0-9./,\s]+',
            f'AllowedIPs = {subnet}',
            content
        )
        
        # Validate the updated config
        from app.services.wireguard import WireGuardService
        is_valid, error_msg, config_data = WireGuardService.validate_config(updated_content)
        
        if not is_valid:
            return False, error_msg, None
        
        # Update the stored config
        config_data['content'] = updated_content
        config_data['status'] = 'validated'
        config_data['updated_at'] = datetime.utcnow().isoformat()
        
        config_path = self._get_config_path(config_id)
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        return True, None, config_data
    
    def delete_pending_config(self, config_id: str) -> bool:
        """Delete a pending config."""
        config_path = self._get_config_path(config_id)
        if os.path.exists(config_path):
            os.remove(config_path)
            return True
        return False
    
    def cleanup_expired_configs(self) -> int:
        """Clean up expired configs and return count of deleted configs."""
        deleted_count = 0
        now = datetime.utcnow()
        
        for filename in os.listdir(self.storage_dir):
            if not filename.endswith('.json'):
                continue
            
            config_path = os.path.join(self.storage_dir, filename)
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            expires_at = datetime.fromisoformat(config_data['expires_at'])
            if now > expires_at:
                os.remove(config_path)
                deleted_count += 1
        
        return deleted_count 