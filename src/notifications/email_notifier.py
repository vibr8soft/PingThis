"""
Email notification system for PingThis application.

This module handles sending email alerts when websites go down or come back up.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from ..config.config_manager import EmailConfig
from ..monitoring.state_manager import UrlStatus, UrlState
from ..utils.logger import get_logger


@dataclass
class EmailTemplate:
    """Email template for notifications."""
    subject: str
    body_text: str
    body_html: Optional[str] = None


class EmailNotifier:
    """Handles email notifications for website status changes."""
    
    def __init__(self, email_config: EmailConfig):
        """
        Initialize the EmailNotifier.
        
        Args:
            email_config: Email configuration settings
        """
        self.config = email_config
        self.logger = get_logger()
    
    def send_down_alert(self, url_status: UrlStatus) -> bool:
        """
        Send a down alert email for a URL.
        
        Args:
            url_status: Status information for the URL that went down
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        template = self._create_down_alert_template(url_status)
        
        success = self._send_email(
            subject=template.subject,
            body_text=template.body_text,
            body_html=template.body_html,
            recipients=self.config.to_emails
        )
        
        if success:
            self.logger.log_email_sent(url_status.url, "DOWN_ALERT", self.config.to_emails)
        
        return success
    
    def send_recovery_alert(self, url_status: UrlStatus) -> bool:
        """
        Send a recovery alert email for a URL.
        
        Args:
            url_status: Status information for the URL that came back up
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        template = self._create_recovery_alert_template(url_status)
        
        success = self._send_email(
            subject=template.subject,
            body_text=template.body_text,
            body_html=template.body_html,
            recipients=self.config.to_emails
        )
        
        if success:
            self.logger.log_email_sent(url_status.url, "UP_RECOVERY", self.config.to_emails)
        
        return success
    
    def send_summary_report(self, url_statuses: List[UrlStatus]) -> bool:
        """
        Send a summary report of all monitored URLs.
        
        Args:
            url_statuses: List of all URL statuses
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        template = self._create_summary_report_template(url_statuses)
        
        success = self._send_email(
            subject=template.subject,
            body_text=template.body_text,
            body_html=template.body_html,
            recipients=self.config.to_emails
        )
        
        if success:
            self.logger.log_email_sent("SUMMARY", "REPORT", self.config.to_emails)
        
        return success
    
    def _send_email(self, subject: str, body_text: str, recipients: List[str], 
                   body_html: Optional[str] = None) -> bool:
        """
        Send an email using SMTP.
        
        Args:
            subject: Email subject
            body_text: Plain text body
            recipients: List of recipient email addresses
            body_html: Optional HTML body
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.config.from_email
            message["To"] = ", ".join(recipients)
            
            # Add plain text part
            text_part = MIMEText(body_text, "plain")
            message.attach(text_part)
            
            # Add HTML part if provided
            if body_html:
                html_part = MIMEText(body_html, "html")
                message.attach(html_part)
            
            # Create SMTP session
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    # Enable security
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                
                # Login and send email
                server.login(self.config.username, self.config.password)
                server.sendmail(self.config.from_email, recipients, message.as_string())
            
            self.logger.debug(f"Email sent successfully to {len(recipients)} recipients")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP authentication failed: {e}")
            return False
            
        except smtplib.SMTPConnectError as e:
            self.logger.error(f"SMTP connection failed: {e}")
            return False
            
        except smtplib.SMTPException as e:
            self.logger.error(f"SMTP error: {e}")
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected error sending email: {e}", exc_info=True)
            return False
    
    def _create_down_alert_template(self, url_status: UrlStatus) -> EmailTemplate:
        """Create email template for down alert."""
        url = url_status.url
        timestamp = url_status.last_state_change.strftime("%Y-%m-%d %H:%M:%S")
        
        subject = f"🚨 ALERT: Website Down - {url}"
        
        body_text = f"""
Website Monitor Alert - Site Down

URL: {url}
Status: DOWN
Time: {timestamp}
Consecutive Failures: {url_status.consecutive_failures}
Total Failures: {url_status.total_failures}
Last Error: {url_status.last_error_message or 'Unknown'}

This website has gone down and is no longer responding correctly.
You will receive a recovery notification when the site comes back online.

--
PingThis Website Monitor
"""
        
        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; margin: 20px;">
    <div style="background-color: #ff4444; color: white; padding: 15px; border-radius: 5px;">
        <h2>🚨 Website Monitor Alert - Site Down</h2>
    </div>
    
    <div style="margin: 20px 0;">
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">URL:</td>
                <td style="padding: 10px; border: 1px solid #ddd;"><a href="{url}">{url}</a></td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Status:</td>
                <td style="padding: 10px; border: 1px solid #ddd; color: #ff4444; font-weight: bold;">DOWN</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Time:</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{timestamp}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Consecutive Failures:</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{url_status.consecutive_failures}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Total Failures:</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{url_status.total_failures}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Last Error:</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{url_status.last_error_message or 'Unknown'}</td>
            </tr>
        </table>
    </div>
    
    <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px;">
        <p><strong>This website has gone down and is no longer responding correctly.</strong></p>
        <p>You will receive a recovery notification when the site comes back online.</p>
    </div>
    
    <div style="margin-top: 20px; font-size: 12px; color: #666;">
        --<br>
        PingThis Website Monitor
    </div>
</body>
</html>
"""
        
        return EmailTemplate(subject=subject, body_text=body_text, body_html=body_html)
    
    def _create_recovery_alert_template(self, url_status: UrlStatus) -> EmailTemplate:
        """Create email template for recovery alert."""
        url = url_status.url
        timestamp = url_status.last_state_change.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate downtime duration
        if url_status.last_state_change and url_status.last_check:
            # This is an approximation - in a real scenario you'd track the down start time
            downtime_duration = "Unknown"  # Could be enhanced with more precise tracking
        else:
            downtime_duration = "Unknown"
        
        subject = f"✅ RECOVERED: Website Back Online - {url}"
        
        body_text = f"""
Website Monitor Alert - Site Recovered

URL: {url}
Status: UP
Recovery Time: {timestamp}
Consecutive Successes: {url_status.consecutive_successes}

Good news! This website is now responding correctly again.
The site has recovered from its previous downtime.

--
PingThis Website Monitor
"""
        
        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; margin: 20px;">
    <div style="background-color: #44aa44; color: white; padding: 15px; border-radius: 5px;">
        <h2>✅ Website Monitor Alert - Site Recovered</h2>
    </div>
    
    <div style="margin: 20px 0;">
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">URL:</td>
                <td style="padding: 10px; border: 1px solid #ddd;"><a href="{url}">{url}</a></td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Status:</td>
                <td style="padding: 10px; border: 1px solid #ddd; color: #44aa44; font-weight: bold;">UP</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Recovery Time:</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{timestamp}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Consecutive Successes:</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{url_status.consecutive_successes}</td>
            </tr>
        </table>
    </div>
    
    <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; color: #2d5a2d;">
        <p><strong>Good news! This website is now responding correctly again.</strong></p>
        <p>The site has recovered from its previous downtime.</p>
    </div>
    
    <div style="margin-top: 20px; font-size: 12px; color: #666;">
        --<br>
        PingThis Website Monitor
    </div>
</body>
</html>
"""
        
        return EmailTemplate(subject=subject, body_text=body_text, body_html=body_html)
    
    def _create_summary_report_template(self, url_statuses: List[UrlStatus]) -> EmailTemplate:
        """Create email template for summary report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate summary statistics
        total_urls = len(url_statuses)
        up_urls = [s for s in url_statuses if s.state == UrlState.UP]
        down_urls = [s for s in url_statuses if s.state == UrlState.DOWN]
        unknown_urls = [s for s in url_statuses if s.state == UrlState.UNKNOWN]
        
        subject = f"📊 PingThis Summary Report - {total_urls} URLs Monitored"
        
        body_text = f"""
PingThis Website Monitor - Summary Report
Generated: {timestamp}

OVERVIEW:
- Total URLs: {total_urls}
- Up: {len(up_urls)}
- Down: {len(down_urls)}
- Unknown: {len(unknown_urls)}

DOWN URLS:
"""
        
        if down_urls:
            for status in down_urls:
                body_text += f"- {status.url} (Failures: {status.consecutive_failures}, Last Error: {status.last_error_message or 'Unknown'})\n"
        else:
            body_text += "- None\n"
        
        body_text += f"""
UP URLS:
"""
        if up_urls:
            for status in up_urls:
                avg_time = f"{status.average_response_time:.3f}s" if status.average_response_time else "N/A"
                body_text += f"- {status.url} (Avg Response: {avg_time})\n"
        else:
            body_text += "- None\n"
        
        body_text += """
--
PingThis Website Monitor
"""
        
        # HTML version with better formatting
        down_urls_html = ""
        if down_urls:
            for status in down_urls:
                down_urls_html += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><a href="{status.url}">{status.url}</a></td>
                    <td style="padding: 8px; border: 1px solid #ddd; color: #ff4444; font-weight: bold;">DOWN</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{status.consecutive_failures}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{status.last_error_message or 'Unknown'}</td>
                </tr>
                """
        else:
            down_urls_html = '<tr><td colspan="4" style="padding: 8px; text-align: center; font-style: italic;">No URLs currently down</td></tr>'
        
        up_urls_html = ""
        if up_urls:
            for status in up_urls:
                avg_time = f"{status.average_response_time:.3f}s" if status.average_response_time else "N/A"
                up_urls_html += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><a href="{status.url}">{status.url}</a></td>
                    <td style="padding: 8px; border: 1px solid #ddd; color: #44aa44; font-weight: bold;">UP</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{status.consecutive_successes}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{avg_time}</td>
                </tr>
                """
        
        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; margin: 20px;">
    <div style="background-color: #4a90e2; color: white; padding: 15px; border-radius: 5px;">
        <h2>📊 PingThis Website Monitor - Summary Report</h2>
        <p>Generated: {timestamp}</p>
    </div>
    
    <div style="margin: 20px 0;">
        <h3>Overview</h3>
        <div style="display: flex; gap: 20px;">
            <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold;">{total_urls}</div>
                <div>Total URLs</div>
            </div>
            <div style="background-color: #e8f5e8; padding: 10px; border-radius: 5px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #44aa44;">{len(up_urls)}</div>
                <div>Up</div>
            </div>
            <div style="background-color: #ffe8e8; padding: 10px; border-radius: 5px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #ff4444;">{len(down_urls)}</div>
                <div>Down</div>
            </div>
            <div style="background-color: #fff8e8; padding: 10px; border-radius: 5px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #cc8800;">{len(unknown_urls)}</div>
                <div>Unknown</div>
            </div>
        </div>
    </div>
    
    {f'''
    <div style="margin: 20px 0;">
        <h3>URLs Currently Down ({len(down_urls)})</h3>
        <table style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background-color: #f0f0f0;">
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">URL</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Status</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Failures</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Last Error</th>
                </tr>
            </thead>
            <tbody>
                {down_urls_html}
            </tbody>
        </table>
    </div>
    ''' if down_urls else ''}
    
    <div style="margin: 20px 0;">
        <h3>URLs Currently Up ({len(up_urls)})</h3>
        <table style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background-color: #f0f0f0;">
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">URL</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Status</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Successes</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Avg Response</th>
                </tr>
            </thead>
            <tbody>
                {up_urls_html}
            </tbody>
        </table>
    </div>
    
    <div style="margin-top: 20px; font-size: 12px; color: #666;">
        --<br>
        PingThis Website Monitor
    </div>
</body>
</html>
"""
        
        return EmailTemplate(subject=subject, body_text=body_text, body_html=body_html)
    
    def test_email_connection(self) -> bool:
        """
        Test the email connection and authentication.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self.logger.info(f"Testing connection to {self.config.smtp_server}:{self.config.smtp_port}")
            self.logger.info(f"Username: {self.config.username}")
            self.logger.info(f"Password length: {len(self.config.password)} characters")
            self.logger.info(f"Using TLS: {self.config.use_tls}")
            
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.set_debuglevel(1)  # Enable SMTP debug output
                
                if self.config.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    self.logger.info("TLS connection established")
                
                server.login(self.config.username, self.config.password)
                self.logger.info("Email connection test successful")
                return True
                
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP Authentication failed: {e}")
            self.logger.error("Troubleshooting tips:")
            self.logger.error("1. Ensure 2-Factor Authentication is enabled on your Gmail account")
            self.logger.error("2. Generate a new App Password (not your regular password)")
            self.logger.error("3. Copy the App Password without spaces")
            self.logger.error("4. For Gmail, use your full email address as username")
            return False
            
        except smtplib.SMTPConnectError as e:
            self.logger.error(f"SMTP Connection failed: {e}")
            self.logger.error("Check your internet connection and SMTP server settings")
            return False
            
        except Exception as e:
            self.logger.error(f"Email connection test failed: {e}")
            return False
