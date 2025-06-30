
import pytest
from unittest.mock import patch, MagicMock
from app.services.route_command_generator import RouteCommandGenerator



@patch('app.services.route_command_generator.RouteCommandGenerator._get_interface_ip', return_value='192.168.1.1')
@patch('app.services.route_command_generator.RouteCommandGenerator._get_lan_interface', return_value='eth0')
def test_generate_route_command_success(mock_get_lan_interface, mock_get_interface_ip):
    success, command = RouteCommandGenerator.generate_route_command('10.0.0.0/24')
    assert success
    assert command == 'ip route add 10.0.0.0/24 via 192.168.1.1 dev eth0'

