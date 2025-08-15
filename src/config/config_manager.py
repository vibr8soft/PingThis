"""
Configuration Manager for PingThis application.

This module handles loading and validating configuration from YAML files.
"""

import yaml
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class EmailConfig:
    """Email configuration settings."""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    from_email: str
    to_emails: List[str]
    use_tls: bool = True


@dataclass
class MonitorConfig:
    """Website monitoring configuration."""
    url: str
    timeout: int = 30
    check_interval: int = 300  # 5 minutes default
    expected_status_codes: List[int] = None
    
    def __post_init__(self):
        if self.expected_status_codes is None:
            self.expected_status_codes = [200, 201, 202, 204]


@dataclass
class AppConfig:
    """Main application configuration."""
    email: EmailConfig
    monitors: List[MonitorConfig]
    log_level: str = "INFO"
    log_file: str = "logs/pingthis.log"
    check_interval: int = 300  # Global default, can be overridden per monitor


class ConfigManager:
    """Manages application configuration from YAML files."""
    
    def __init__(self, config_path: str):
        """
        Initialize ConfigManager with path to configuration file.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """
        Load configuration from YAML file.
        
        Returns:
            AppConfig: Loaded and validated configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
            ValueError: If required configuration is missing
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
            
            self._config = self._parse_config(config_data)
            self._validate_config(self._config)
            
            return self._config
            
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in config file: {e}")
    
    def _parse_config(self, config_data: Dict[str, Any]) -> AppConfig:
        """Parse raw configuration data into typed objects."""
        # Parse email configuration
        email_data = config_data.get('email', {})
        email_config = EmailConfig(
            smtp_server=email_data.get('smtp_server'),
            smtp_port=email_data.get('smtp_port', 587),
            username=email_data.get('username'),
            password=email_data.get('password'),
            from_email=email_data.get('from_email'),
            to_emails=email_data.get('to_emails', []),
            use_tls=email_data.get('use_tls', True)
        )
        
        # Parse monitor configurations
        monitors_data = config_data.get('monitors', [])
        monitors = []
        
        for monitor_data in monitors_data:
            monitor = MonitorConfig(
                url=monitor_data.get('url'),
                timeout=monitor_data.get('timeout', 30),
                check_interval=monitor_data.get('check_interval', 
                                              config_data.get('check_interval', 300)),
                expected_status_codes=monitor_data.get('expected_status_codes')
            )
            monitors.append(monitor)
        
        # Create main config
        return AppConfig(
            email=email_config,
            monitors=monitors,
            log_level=config_data.get('log_level', 'INFO'),
            log_file=config_data.get('log_file', 'logs/pingthis.log'),
            check_interval=config_data.get('check_interval', 300)
        )
    
    def _validate_config(self, config: AppConfig) -> None:
        """
        Validate configuration for required fields and logical consistency.
        
        Args:
            config: Configuration to validate
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate email config
        email = config.email
        if not email.smtp_server:
            raise ValueError("Email SMTP server is required")
        if not email.username:
            raise ValueError("Email username is required")
        if not email.password:
            raise ValueError("Email password is required")
        if not email.from_email:
            raise ValueError("From email address is required")
        if not email.to_emails:
            raise ValueError("At least one recipient email is required")
        
        # Validate monitors
        if not config.monitors:
            raise ValueError("At least one monitor configuration is required")
        
        for i, monitor in enumerate(config.monitors):
            if not monitor.url:
                raise ValueError(f"Monitor {i}: URL is required")
            if not monitor.url.startswith(('http://', 'https://')):
                raise ValueError(f"Monitor {i}: URL must start with http:// or https://")
            if monitor.timeout <= 0:
                raise ValueError(f"Monitor {i}: Timeout must be positive")
            if monitor.check_interval <= 0:
                raise ValueError(f"Monitor {i}: Check interval must be positive")
    
    @property
    def config(self) -> Optional[AppConfig]:
        """Get the loaded configuration."""
        return self._config
    
    def get_monitor_by_url(self, url: str) -> Optional[MonitorConfig]:
        """
        Get monitor configuration by URL.
        
        Args:
            url: URL to search for
            
        Returns:
            MonitorConfig if found, None otherwise
        """
        if not self._config:
            return None
            
        for monitor in self._config.monitors:
            if monitor.url == url:
                return monitor
        return None
