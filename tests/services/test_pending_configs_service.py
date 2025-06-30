
import pytest
import os
import json
from unittest.mock import patch, MagicMock
from app.services.pending_configs import PendingConfigsService

@pytest.fixture
def pending_configs_service(tmp_path):
    """Fixture to create a PendingConfigsService instance in a temporary directory."""
    return PendingConfigsService(storage_dir=str(tmp_path))

# --- Test Data ---
CONFIG_CONTENT = """
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=
Address = 10.0.0.2/32

[Peer]
PublicKey = BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBA=
AllowedIPs = 0.0.0.0/0
Endpoint = 1.2.3.4:51820
"""

# --- Tests for store_pending_config ---

def test_store_and_get_pending_config(pending_configs_service):
    config_id = pending_configs_service.store_pending_config(CONFIG_CONTENT)
    assert config_id is not None
    
    retrieved_config = pending_configs_service.get_pending_config(config_id)
    assert retrieved_config is not None
    assert retrieved_config['content'] == CONFIG_CONTENT

# --- Tests for update_config_with_subnet ---

def test_update_config_with_subnet_success(pending_configs_service):
    config_id = pending_configs_service.store_pending_config(CONFIG_CONTENT)
    
    with patch('app.services.wireguard.WireGuardService.validate_config') as mock_validate:
        mock_validate.return_value = (True, None, {'public_key': 'test_key'})
        success, error, updated_config = pending_configs_service.update_config_with_subnet(config_id, '192.168.1.0/24')
    
    assert success
    assert error is None
    assert 'AllowedIPs = 192.168.1.0/24' in updated_config['content']

def test_update_config_with_subnet_validation_failure(pending_configs_service):
    config_id = pending_configs_service.store_pending_config(CONFIG_CONTENT)
    
    with patch('app.services.wireguard.WireGuardService.validate_config') as mock_validate:
        mock_validate.return_value = (False, 'Invalid subnet', None)
        success, error, _ = pending_configs_service.update_config_with_subnet(config_id, 'invalid-subnet')
    
    assert not success
    assert 'Invalid subnet' in error

# --- Tests for delete_pending_config ---

def test_delete_pending_config(pending_configs_service):
    config_id = pending_configs_service.store_pending_config(CONFIG_CONTENT)
    config_path = pending_configs_service._get_config_path(config_id)
    assert os.path.exists(config_path)
    
    pending_configs_service.delete_pending_config(config_id)
    assert not os.path.exists(config_path)

