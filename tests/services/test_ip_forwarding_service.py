
import pytest
from unittest.mock import patch, MagicMock, mock_open
from app.services.ip_forwarding import IPForwardingService

@patch('subprocess.run')
@patch('builtins.open', new_callable=mock_open, read_data='1') # Only return '1' for simplicity
def test_check_status_enabled(mock_open, mock_run):
    assert IPForwardingService.check_status()

@patch('subprocess.run')
@patch('builtins.open', new_callable=mock_open, read_data='0') # Only return '0'
def test_check_status_disabled(mock_open, mock_run):
    assert not IPForwardingService.check_status()

@patch('subprocess.run')
def test_enable_temporary_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    success, _ = IPForwardingService.enable_temporary()
    assert success

@patch('builtins.open', new_callable=mock_open, read_data='net.ipv4.ip_forward=0')
@patch('app.services.ip_forwarding.IPForwardingService.enable_temporary', return_value=(True, ''))
@patch('subprocess.run')
def test_enable_permanent_success(mock_run, mock_enable_temp, mock_open_file):
    mock_run.return_value = MagicMock(returncode=0)
    success, _ = IPForwardingService.enable_permanent()
    assert success

