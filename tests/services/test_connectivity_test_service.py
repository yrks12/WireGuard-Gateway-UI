
import pytest
from unittest.mock import patch, MagicMock
from app.services.connectivity_test import ConnectivityTestService
from app.services.wireguard import WireGuardService # Import WireGuardService

@patch('subprocess.run')
def test_test_connectivity_success(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='64 bytes from 1.1.1.1: icmp_seq=1 ttl=58 time=10.0 ms'
    )
    success, result = ConnectivityTestService.test_connectivity('1.1.1.1')
    assert success
    assert result['latency_ms'] == 10.0

@patch('subprocess.run')
def test_test_connectivity_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr='Request timed out.')
    success, result = ConnectivityTestService.test_connectivity('1.1.1.1')
    assert not success
    assert 'All ping attempts failed' in result['error']

@patch('app.services.connectivity_test.ConnectivityTestService._get_allowed_ips')
@patch('app.services.connectivity_test.ConnectivityTestService.test_connectivity')
def test_test_client_connectivity(mock_test_connectivity, mock_get_allowed_ips):
    mock_test_connectivity.return_value = (True, {'success': True, 'latency_ms': 20.0})
    mock_get_allowed_ips.return_value = ['192.168.1.1/24']
    
    mock_config_storage = MagicMock()
    mock_config_storage.get_client.return_value = {'subnet': '192.168.1.1/24', 'config_path': '/etc/wireguard/test.conf'}
    
    success, result = ConnectivityTestService.test_client_connectivity('client1', mock_config_storage)
    
    assert success
    assert result['latency_ms'] == 20.0
    mock_test_connectivity.assert_called_with('192.168.1.1/24')

