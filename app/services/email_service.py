import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Optional, List
from flask import current_app

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending email alerts."""
    
    @staticmethod
    def send_email(
        subject: str,
        body: str,
        recipients: List[str],
        is_html: bool = False
    ) -> bool:
        """
        Send an email using the configured SMTP settings.
        Returns True if successful, False otherwise.
        """
        try:
            # Get email settings from app config
            smtp_host = current_app.config.get('SMTP_HOST')
            smtp_port = current_app.config.get('SMTP_PORT')
            smtp_username = current_app.config.get('SMTP_USERNAME')
            smtp_password = current_app.config.get('SMTP_PASSWORD')
            smtp_from = current_app.config.get('SMTP_FROM')
            
            if not all([smtp_host, smtp_port, smtp_username, smtp_password, smtp_from]):
                logger.error("SMTP settings not configured")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = smtp_from
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Add body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if current_app.config.get('SMTP_USE_TLS', True):
                    server.starttls()
                
                # Login
                server.login(smtp_username, smtp_password)
                
                # Send email
                server.send_message(msg)
                
                return True
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    @staticmethod
    def send_alert(
        subject: str,
        message: str,
        recipients: Optional[List[str]] = None,
        is_html: bool = False
    ) -> bool:
        """
        Send an alert email. If recipients is None, uses the configured alert recipients.
        """
        if recipients is None:
            recipients = current_app.config.get('ALERT_RECIPIENTS', [])
        
        if not recipients:
            logger.warning("No recipients specified for alert")
            return False
            
        return EmailService.send_email(
            subject=f"[WireGuard Gateway Alert] {subject}",
            body=message,
            recipients=recipients,
            is_html=is_html
        ) 