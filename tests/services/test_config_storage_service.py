
import pytest
import os
import json
from unittest.mock import patch, MagicMock
from app.services.config_storage import ConfigStorageService

@pytest.fixture
def config_storage_service(tmp_path):
    """Fixture to create a ConfigStorageService instance in a temporary directory."""
    db_path = tmp_path / "test.db"
    return ConfigStorageService(storage_dir=str(tmp_path), db_path=str(db_path))

# Mock pwd and grp modules for testing on non-Linux systems
# Also mock os.chmod and os.chown as these are system-level operations
@pytest.fixture(autouse=True)
def mock_system_calls():
    with patch('pwd.getpwnam', return_value=MagicMock(pw_uid=1000)),          patch('grp.getgrnam', return_value=MagicMock(gr_gid=1000)),          patch('os.chmod'),          patch('os.chown'):
        yield

@pytest.fixture(autouse=True)
def mock_etc_wireguard_writes():
    original_open = open
    original_os_remove = os.remove

    def mock_open_for_wireguard(file, mode='r', *args, **kwargs):
        if '/etc/wireguard' in file:
            return MagicMock() # Return a mock file object
        return original_open(file, mode, *args, **kwargs)

    def mock_os_remove_for_wireguard(path, *args, **kwargs):
        if '/etc/wireguard' in path:
            pass # Do nothing for /etc/wireguard paths
        else:
            original_os_remove(path, *args, **kwargs)

    with patch('builtins.open', side_effect=mock_open_for_wireguard),          patch('os.remove', side_effect=mock_os_remove_for_wireguard):
        yield




# --- Test Data ---
CONFIG_CONTENT = """
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=
Address = 10.0.0.2/32

[Peer]
PublicKey = BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBA=
AllowedIPs = 192.168.1.0/24
Endpoint = 1.2.3.4:51820
"""
SUBNET = "192.168.1.0/24"
PUBLIC_KEY = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBA="

# --- Tests for store_config ---

def test_store_config(config_storage_service):
    client_id, metadata = config_storage_service.store_config(CONFIG_CONTENT, SUBNET, PUBLIC_KEY, 'test.conf')
    
    assert client_id is not None
    assert metadata['name'].startswith('test')
    assert metadata['subnet'] == SUBNET
    assert metadata['public_key'] == PUBLIC_KEY
    # Construct the expected path in the temporary storage directory
    expected_config_path_in_storage_dir = os.path.join(config_storage_service.storage_dir, os.path.basename(metadata['config_path']))
    assert os.path.exists(expected_config_path_in_storage_dir)
    
    # Verify metadata was saved
    client = config_storage_service.get_client(client_id)
    assert client is not None

# --- Tests for get_client and list_clients ---

def test_get_and_list_clients(config_storage_service):
    client_id, _ = config_storage_service.store_config(CONFIG_CONTENT, SUBNET, PUBLIC_KEY)
    
    client = config_storage_service.get_client(client_id)
    assert client is not None
    assert client['id'] == client_id
    
    clients = config_storage_service.list_clients()
    assert len(clients) == 1
    assert clients[0]['id'] == client_id

# --- Tests for delete_client ---

def test_delete_client(config_storage_service):
    client_id, metadata = config_storage_service.store_config(CONFIG_CONTENT, SUBNET, PUBLIC_KEY)
    config_path = metadata['config_path']
    
    # The test will not have permissions to check for the file in /etc/wireguard
    # assert os.path.exists(config_path)
    
    config_storage_service.delete_client(client_id)
    
    # Construct the expected path in the temporary storage directory
    expected_config_path_in_storage_dir = os.path.join(config_storage_service.storage_dir, os.path.basename(config_path))
    assert not os.path.exists(expected_config_path_in_storage_dir)
    assert config_storage_service.get_client(client_id) is None

# --- Tests for update_client_status ---

def test_update_client_status(config_storage_service):
    client_id, _ = config_storage_service.store_config(CONFIG_CONTENT, SUBNET, PUBLIC_KEY)
    
    config_storage_service.update_client_status(client_id, 'active')
    client = config_storage_service.get_client(client_id)
    assert client['status'] == 'active'

# --- Tests for test_history ---

def test_add_and_get_test_history(config_storage_service):
    client_id, _ = config_storage_service.store_config(CONFIG_CONTENT, SUBNET, PUBLIC_KEY)
    
    config_storage_service.add_test_result(client_id, 123, True, '1.1.1.1')
    history = config_storage_service.get_test_history(client_id)
    
    assert len(history) == 1
    assert history[0]['latency_ms'] == 123
    assert history[0]['success']

