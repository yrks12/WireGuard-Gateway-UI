
import pytest
from unittest.mock import patch, MagicMock
from app.services.dns_resolver import DNSResolver
from app.services.auto_reconnect import AutoReconnectService

@pytest.fixture(autouse=True)
def clear_dns_resolver_status():
    DNSResolver._hostname_status = {}

# --- Tests for DNSResolver ---

@patch('socket.gethostbyname')
def test_resolve_hostname_success(mock_gethostbyname):
    mock_gethostbyname.return_value = '1.2.3.4'
    ip = DNSResolver.resolve_hostname('test.com')
    assert ip == '1.2.3.4'

@patch('socket.gethostbyname', side_effect=Exception('Resolution failed'))
def test_resolve_hostname_failure(mock_gethostbyname):
    ip = DNSResolver.resolve_hostname('test.com')
    assert ip is None

# --- Tests for AutoReconnectService ---

@patch('app.services.wireguard.WireGuardService.deactivate_client')
@patch('app.services.wireguard.WireGuardService.activate_client')
def test_reconnect_client(mock_activate, mock_deactivate):
    mock_deactivate.return_value = (True, None)
    mock_activate.return_value = (True, None)
    
    mock_config_storage = MagicMock()
    client = {'id': 'client1', 'name': 'test-client', 'config_path': '/fake/path'}
    
    reconnected = AutoReconnectService._reconnect_client(client, mock_config_storage)
    
    assert reconnected
    mock_deactivate.assert_called_once()
    mock_activate.assert_called_once()

