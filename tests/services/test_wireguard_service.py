

import pytest
from unittest.mock import patch, MagicMock
from app.services.wireguard import WireGuardService

# --- Test Data ---
VALID_CONFIG = """
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=
Address = 10.0.0.2/32

[Peer]
PublicKey = BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBA=
AllowedIPs = 192.168.1.0/24
Endpoint = 1.2.3.4:51820
"""

INVALID_CONFIG_NO_PEER = """
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=
Address = 10.0.0.2/32
"""

INVALID_CONFIG_BAD_KEY = """
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=
Address = 10.0.0.2/32

[Peer]
PublicKey = not-a-key
AllowedIPs = 192.168.1.0/24
Endpoint = 1.2.3.4:51820
"""

CONFIG_WITH_0_0_0_0 = """
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=
Address = 10.0.0.2/32

[Peer]
PublicKey = BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBA=
AllowedIPs = 0.0.0.0/0
Endpoint = 1.2.3.4:51820
"""

# --- Tests for validate_config ---

def test_validate_config_valid():
    is_valid, error_msg, config_data = WireGuardService.validate_config(VALID_CONFIG)
    assert is_valid
    assert error_msg is None
    assert config_data['public_key'] == 'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBA='
    assert '192.168.1.0/24' in config_data['subnets']

def test_validate_config_missing_peer():
    is_valid, error_msg, _ = WireGuardService.validate_config(INVALID_CONFIG_NO_PEER)
    assert not is_valid
    assert "Missing [Peer] section" in error_msg

def test_validate_config_invalid_key():
    is_valid, error_msg, _ = WireGuardService.validate_config(INVALID_CONFIG_BAD_KEY)
    assert not is_valid
    assert "Invalid or missing PublicKey" in error_msg

def test_validate_config_with_zero_subnet():
    is_valid, error_msg, _ = WireGuardService.validate_config(CONFIG_WITH_0_0_0_0)
    assert not is_valid
    assert "AllowedIPs cannot be 0.0.0.0/0" in error_msg

# --- Tests for activate_client and deactivate_client ---

@patch('subprocess.run')
def test_activate_client_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr='')
    success, error = WireGuardService.activate_client('/fake/path/wg0.conf')
    assert success
    assert error is None
    mock_run.assert_called_with(['sudo', 'wg-quick', 'up', '/fake/path/wg0.conf'], capture_output=True, text=True)

@patch('subprocess.run')
def test_activate_client_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr='test error')
    success, error = WireGuardService.activate_client('/fake/path/wg0.conf')
    assert not success
    assert "test error" in error

@patch('subprocess.run')
def test_deactivate_client_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr='')
    success, error = WireGuardService.deactivate_client('/fake/path/wg0.conf')
    assert success
    assert error is None
    mock_run.assert_called_with(['sudo', 'wg-quick', 'down', '/fake/path/wg0.conf'], capture_output=True, text=True)

@patch('subprocess.run')
def test_deactivate_client_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr='test error')
    success, error = WireGuardService.deactivate_client('/fake/path/wg0.conf')
    assert not success
    assert "test error" in error

# --- Tests for get_client_status ---

@patch('subprocess.run')
def test_get_client_status_connected(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='interface: wg0\n  public key: ...\n  private key: (hidden)\n  listening port: 51820\n\npeer: BBBBB...\n  endpoint: 1.2.3.4:51820\n  allowed ips: 192.168.1.0/24\n  latest handshake: 1 minute, 2 seconds ago\n  transfer: 1.23 GiB received, 4.56 GiB sent\n'
    )
    status = WireGuardService.get_client_status('wg0')
    assert 'error' not in status
    assert status['connected']
    assert status['last_handshake'] == '1 minute, 2 seconds ago'

@patch('subprocess.run')
def test_get_client_status_disconnected(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='interface: wg0\n  public key: ...\n  private key: (hidden)\n  listening port: 51820\n'
    )
    status = WireGuardService.get_client_status('wg0')
    assert not status['connected']
    assert status['last_handshake'] is None

@patch('subprocess.run')
def test_get_client_status_error(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr='No such device')
    status = WireGuardService.get_client_status('wg0')
    assert 'error' in status
    assert "No such device" in status['error']


