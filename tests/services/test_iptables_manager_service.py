

import pytest
from unittest.mock import patch, MagicMock
from app.services.iptables_manager import IptablesManager
import subprocess

# --- Mocks for subprocess ---

@patch('app.services.iptables_manager.IptablesManager._get_lan_interface', return_value='eth0')
@patch('subprocess.run')
def test_setup_forwarding_success(mock_run, mock_get_lan_interface):
    mock_run.return_value = MagicMock(returncode=0)
    success, error = IptablesManager.setup_forwarding('wg0')
    assert success
    assert error is None
    # Check that all iptables commands were called
    assert mock_run.call_count == 4

@patch('app.services.iptables_manager.IptablesManager._get_lan_interface', return_value='eth0')
@patch('subprocess.run')
def test_setup_forwarding_failure(mock_run, mock_get_lan_interface):
    mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr='error')
    success, error = IptablesManager.setup_forwarding('wg0')
    assert not success
    assert "Failed to enable IP forwarding" in error or "Failed to add iptables rule" in error

@patch('app.services.iptables_manager.IptablesManager._get_lan_interface', return_value='eth0')
@patch('subprocess.run')
def test_cleanup_forwarding_success(mock_run, mock_get_lan_interface):
    mock_run.return_value = MagicMock(returncode=0)
    success, error = IptablesManager.cleanup_forwarding('wg0')
    assert success
    assert error is None
    assert mock_run.call_count == 3
    mock_run.side_effect = [
        MagicMock(
            returncode=0,
            stdout='Chain POSTROUTING (policy ACCEPT 0 packets, 0 bytes)\n'
                   ' pkts bytes target     prot opt in     out     source               destination\n'
                   '    0     0 MASQUERADE  all  --  *      wg0     0.0.0.0/0            0.0.0.0/0\n'
        ),
        MagicMock(
            returncode=0,
            stdout='Chain FORWARD (policy ACCEPT 0 packets, 0 bytes)\n'
                   ' pkts bytes target     prot opt in     out     source               destination\n'
                   '   0    0 ACCEPT     all  --  wg0    eth0    0.0.0.0/0            0.0.0.0/0\n'
                   '   0    0 ACCEPT     all  --  eth0   wg0     0.0.0.0/0            0.0.0.0/0 state RELATED,ESTABLISHED\n'
        )
    ]
    success, rules, error = IptablesManager.get_forwarding_rules('wg0')
    assert success
    assert len(rules['nat']) == 1
    assert 'MASQUERADE' in rules['nat'][0]
    assert len(rules['forward']) == 2
    assert 'ACCEPT' in rules['forward'][0]
    assert 'ACCEPT' in rules['forward'][1]
    assert 'wg0' in rules['nat'][0]
    assert 'wg0' in rules['forward'][0]
    assert 'wg0' in rules['forward'][1]

@patch('app.services.iptables_manager.IptablesManager._get_lan_interface', return_value='eth0')
@patch('app.services.iptables_manager.IptablesManager._get_interface_ip', return_value='10.0.0.1')
@patch('subprocess.run')
def test_get_router_command(mock_run, mock_get_lan_interface, mock_get_interface_ip):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='inet 10.0.0.1/24 brd 10.0.0.255 scope global wg0\n'
    )
    command = IptablesManager.get_router_command('wg0', '192.168.2.0/24')
    assert command == 'ip route add 192.168.2.0/24 via 10.0.0.1 dev eth0'



