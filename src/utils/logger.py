"""
Logging utility for PingThis application.

This module provides centralized logging functionality with file and console output.
"""

import logging
import os
from datetime import datetime
from typing import Optional


class PingThisLogger:
    """Custom logger for PingThis application."""
    
    def __init__(self, log_file: str = "logs/pingthis.log", log_level: str = "INFO"):
        """
        Initialize the logger.
        
        Args:
            log_file: Path to the log file
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_file = log_file
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = None
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Set up the logger with file and console handlers."""
        # Create logger
        self.logger = logging.getLogger('PingThis')
        self.logger.setLevel(self.log_level)
        
        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Create and configure file handler
        try:
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            print(f"Warning: Could not create log file {self.log_file}: {e}")
        
        # Create and configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, url: Optional[str] = None) -> None:
        """Log an info message."""
        if url:
            message = f"[{url}] {message}"
        self.logger.info(message)
    
    def warning(self, message: str, url: Optional[str] = None) -> None:
        """Log a warning message."""
        if url:
            message = f"[{url}] {message}"
        self.logger.warning(message)
    
    def error(self, message: str, url: Optional[str] = None, exc_info: bool = False) -> None:
        """Log an error message."""
        if url:
            message = f"[{url}] {message}"
        self.logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str, url: Optional[str] = None) -> None:
        """Log a debug message."""
        if url:
            message = f"[{url}] {message}"
        self.logger.debug(message)
    
    def critical(self, message: str, url: Optional[str] = None) -> None:
        """Log a critical message."""
        if url:
            message = f"[{url}] {message}"
        self.logger.critical(message)
    
    def log_ping_result(self, url: str, success: bool, response_time: Optional[float] = None, 
                       status_code: Optional[int] = None, error_message: Optional[str] = None) -> None:
        """
        Log a ping result with structured information.
        
        Args:
            url: The URL that was pinged
            success: Whether the ping was successful
            response_time: Response time in seconds
            status_code: HTTP status code returned
            error_message: Error message if ping failed
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if success:
            message = f"PING SUCCESS - Status: {status_code}"
            if response_time is not None:
                message += f", Response time: {response_time:.3f}s"
            self.info(message, url)
        else:
            message = f"PING FAILED"
            if status_code is not None:
                message += f" - Status: {status_code}"
            if response_time is not None:
                message += f", Response time: {response_time:.3f}s"
            if error_message:
                message += f", Error: {error_message}"
            self.error(message, url)
    
    def log_state_change(self, url: str, old_state: str, new_state: str) -> None:
        """
        Log a state change for a monitored URL.
        
        Args:
            url: The URL whose state changed
            old_state: Previous state (UP/DOWN)
            new_state: New state (UP/DOWN)
        """
        self.warning(f"STATE CHANGE: {old_state} -> {new_state}", url)
    
    def log_email_sent(self, url: str, email_type: str, recipients: list) -> None:
        """
        Log when an email notification is sent.
        
        Args:
            url: The URL related to the notification
            email_type: Type of email (DOWN_ALERT, UP_RECOVERY)
            recipients: List of email recipients
        """
        recipients_str = ", ".join(recipients)
        self.info(f"EMAIL SENT - Type: {email_type}, Recipients: {recipients_str}", url)
    
    def log_startup(self, monitors_count: int, check_interval: int) -> None:
        """
        Log application startup information.
        
        Args:
            monitors_count: Number of monitors configured
            check_interval: Check interval in seconds
        """
        self.info(f"PingThis started - Monitoring {monitors_count} URLs, "
                 f"Check interval: {check_interval}s")
    
    def log_shutdown(self) -> None:
        """Log application shutdown."""
        self.info("PingThis shutting down")


# Global logger instance
_logger_instance: Optional[PingThisLogger] = None


def get_logger(log_file: str = "logs/pingthis.log", log_level: str = "INFO") -> PingThisLogger:
    """
    Get the global logger instance.
    
    Args:
        log_file: Path to the log file (used only on first call)
        log_level: Logging level (used only on first call)
        
    Returns:
        PingThisLogger instance
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = PingThisLogger(log_file, log_level)
    
    return _logger_instance


def initialize_logger(log_file: str = "logs/pingthis.log", log_level: str = "INFO") -> PingThisLogger:
    """
    Initialize the global logger instance.
    
    Args:
        log_file: Path to the log file
        log_level: Logging level
        
    Returns:
        PingThisLogger instance
    """
    global _logger_instance
    _logger_instance = PingThisLogger(log_file, log_level)
    return _logger_instance
