
import pytest
from unittest.mock import patch, MagicMock
from app.services.status_poller import StatusPoller

@patch('psutil.cpu_percent')
@patch('psutil.virtual_memory')
@patch('psutil.disk_usage')
def test_get_system_metrics(mock_disk, mock_mem, mock_cpu):
    mock_cpu.return_value = 50.0
    mock_mem.return_value = MagicMock(percent=60.0, used=2*1024*1024, total=4*1024*1024)
    mock_disk.return_value = MagicMock(percent=70.0, used=10*1024*1024*1024, total=20*1024*1024*1024)
    
    metrics = StatusPoller.get_system_metrics()
    
    assert metrics['cpu_percent'] == 50.0
    assert metrics['memory_percent'] == 60.0
    assert metrics['disk_percent'] == 70.0

