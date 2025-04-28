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
            smtp_use_tls = current_app.config.get('SMTP_USE_TLS', True)
            
            logger.info(f"Attempting to send email with settings: host={smtp_host}, port={smtp_port}, from={smtp_from}")
            logger.info(f"Recipients: {recipients}")
            
            if not all([smtp_host, smtp_port, smtp_from]):
                logger.error("Required SMTP settings not configured")
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
            logger.info(f"Connecting to SMTP server {smtp_host}:{smtp_port}")
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                # Start TLS if required
                if smtp_use_tls:
                    logger.info("Starting TLS connection")
                    server.starttls()
                
                # Only attempt login if credentials are provided
                if smtp_username and smtp_password:
                    try:
                        logger.info("Attempting SMTP login")
                server.login(smtp_username, smtp_password)
                        logger.info("SMTP login successful")
                    except smtplib.SMTPNotSupportedError:
                        logger.warning("SMTP server does not support authentication, proceeding without login")
                    except Exception as e:
                        logger.error(f"SMTP login failed: {e}")
                        return False
                
                # Send email
                logger.info("Sending email message")
                server.send_message(msg)
                logger.info("Email sent successfully")
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
            logger.info(f"Using configured alert recipients: {recipients}")
        
        if not recipients:
            logger.warning("No recipients specified for alert")
            return False
            
        return EmailService.send_email(
            subject=f"[WireGuard Gateway Alert] {subject}",
            body=message,
            recipients=recipients,
            is_html=is_html
        ) 