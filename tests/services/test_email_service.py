
import pytest
from unittest.mock import patch, MagicMock
from app.services.email_service import EmailService

@pytest.fixture
def mock_current_app():
    """Fixture to create a mock Flask app with email configuration."""
    app = MagicMock()
    app.config = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': 587,
        'SMTP_USE_TLS': True,
        'SMTP_USERNAME': 'user',
        'SMTP_PASSWORD': 'pass',
        'SMTP_FROM': 'from@test.com',
        'ALERT_RECIPIENTS': ['to@test.com']
    }
    return app

@patch('smtplib.SMTP')
def test_send_alert_success(mock_smtp, mock_current_app):
    with patch('app.services.email_service.current_app', mock_current_app):
        server_mock = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server_mock
        
        success = EmailService.send_alert('Test Subject', 'Test Message')
        
        assert success
        server_mock.starttls.assert_called_once()
        server_mock.login.assert_called_with('user', 'pass')
        server_mock.send_message.assert_called_once()

@patch('smtplib.SMTP', side_effect=Exception('Connection failed'))
def test_send_alert_failure(mock_smtp, mock_current_app):
    with patch('app.services.email_service.current_app', mock_current_app):
        success = EmailService.send_alert('Test Subject', 'Test Message')
        assert not success

