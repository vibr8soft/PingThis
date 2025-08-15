"""
Main application for PingThis website monitoring system.

This module orchestrates all components to monitor websites and send alerts.
"""

import signal
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

from .config.config_manager import ConfigManager, AppConfig
from .monitoring.ping_checker import PingChecker, HealthChecker
from .monitoring.state_manager import StateManager, UrlStatus
from .notifications.email_notifier import EmailNotifier
from .utils.logger import initialize_logger, get_logger


class PingThisApplication:
    """Main application class that coordinates website monitoring."""
    
    def __init__(self, config_path: str):
        """
        Initialize the PingThis application.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config: Optional[AppConfig] = None
        self.logger = None
        
        # Core components
        self.config_manager = ConfigManager(config_path)
        self.state_manager = None
        self.ping_checker = None
        self.health_checker = None
        self.email_notifier = None
        
        # Runtime control
        self.running = False
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize(self) -> bool:
        """
        Initialize the application components.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Load configuration
            self.config = self.config_manager.load_config()
            
            # Initialize logger with config settings
            self.logger = initialize_logger(
                log_file=self.config.log_file,
                log_level=self.config.log_level
            )
            
            self.logger.info("Initializing PingThis application...")
            
            # Initialize state manager
            self.state_manager = StateManager()
            
            # Initialize ping components
            self.ping_checker = PingChecker()
            self.health_checker = HealthChecker()
            
            # Initialize email notifier
            self.email_notifier = EmailNotifier(self.config.email)
            
            # Test email connection
            self.logger.info("Testing email connection...")
            if not self.email_notifier.test_email_connection():
                self.logger.error("Email connection test failed. Please check your email configuration.")
                return False
            
            self.logger.info("Email connection test successful")
            
            # Log startup information
            self.logger.log_startup(
                monitors_count=len(self.config.monitors),
                check_interval=self.config.check_interval
            )
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize application: {e}", exc_info=True)
            else:
                print(f"Failed to initialize application: {e}")
            return False
    
    def start(self) -> None:
        """Start the monitoring application."""
        if not self.initialize():
            sys.exit(1)
        
        self.running = True
        self.logger.info("Starting PingThis monitoring...")
        
        try:
            # Start monitoring threads for each URL
            for monitor_config in self.config.monitors:
                thread = threading.Thread(
                    target=self._monitor_url,
                    args=(monitor_config,),
                    name=f"Monitor-{monitor_config.url}",
                    daemon=True
                )
                thread.start()
                self.monitor_threads[monitor_config.url] = thread
                self.logger.info(f"Started monitoring thread for {monitor_config.url}")
            
            # Start cleanup thread
            cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                name="Cleanup-Worker",
                daemon=True
            )
            cleanup_thread.start()
            
            # Main loop - wait for shutdown
            while self.running and not self.shutdown_event.is_set():
                try:
                    self.shutdown_event.wait(timeout=30.0)
                except KeyboardInterrupt:
                    break
            
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        
        finally:
            self._shutdown()
    
    def _monitor_url(self, monitor_config) -> None:
        """
        Monitor a single URL in a loop.
        
        Args:
            monitor_config: Configuration for the URL to monitor
        """
        url = monitor_config.url
        check_interval = monitor_config.check_interval
        
        self.logger.debug(f"Starting URL monitor loop", url)
        
        while self.running and not self.shutdown_event.is_set():
            try:
                # Perform health check
                is_healthy, ping_result = self.health_checker.is_url_healthy(monitor_config)
                
                # Update state and check for alerts
                state_changed, should_send_alert = self.state_manager.update_url_status(ping_result)
                
                if should_send_alert:
                    url_status = self.state_manager.get_url_status(url)
                    if url_status:
                        self._handle_alert(url_status)
                
                # Wait for next check
                if self.shutdown_event.wait(timeout=check_interval):
                    break  # Shutdown requested
                    
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}", url, exc_info=True)
                # Wait a bit before retrying to avoid tight error loops
                if self.shutdown_event.wait(timeout=60):
                    break
        
        self.logger.debug(f"Exiting URL monitor loop", url)
    
    def _handle_alert(self, url_status: UrlStatus) -> None:
        """
        Handle sending alerts for URL status changes.
        
        Args:
            url_status: URL status that triggered the alert
        """
        try:
            if url_status.state.value == "DOWN" and url_status.alert_sent and not url_status.recovery_alert_sent:
                # This is a down alert (should have been sent already by state manager logic)
                self.logger.debug(f"Processing DOWN alert", url_status.url)
                success = self.email_notifier.send_down_alert(url_status)
                if not success:
                    self.logger.error(f"Failed to send down alert", url_status.url)
                    
            elif url_status.state.value == "UP" and url_status.recovery_alert_sent and url_status.alert_sent:
                # This is a recovery alert
                self.logger.debug(f"Processing RECOVERY alert", url_status.url)
                success = self.email_notifier.send_recovery_alert(url_status)
                if not success:
                    self.logger.error(f"Failed to send recovery alert", url_status.url)
                    
        except Exception as e:
            self.logger.error(f"Error handling alert: {e}", url_status.url, exc_info=True)
    
    def _cleanup_worker(self) -> None:
        """Worker thread for periodic cleanup tasks."""
        self.logger.debug("Starting cleanup worker thread")
        
        # Run cleanup every 6 hours
        cleanup_interval = 6 * 60 * 60  # 6 hours in seconds
        
        while self.running and not self.shutdown_event.is_set():
            try:
                # Wait for cleanup interval or shutdown
                if self.shutdown_event.wait(timeout=cleanup_interval):
                    break  # Shutdown requested
                
                # Perform cleanup
                self.logger.debug("Running periodic cleanup...")
                
                # Clean up old state (older than 30 days)
                cleaned_count = self.state_manager.cleanup_old_state(max_age_days=30)
                if cleaned_count > 0:
                    self.logger.info(f"Cleaned up {cleaned_count} old URL states")
                
                self.logger.debug("Periodic cleanup completed")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup worker: {e}", exc_info=True)
        
        self.logger.debug("Exiting cleanup worker thread")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        signal_names = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}
        signal_name = signal_names.get(signum, f"Signal {signum}")
        
        if self.logger:
            self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        else:
            print(f"Received {signal_name}, shutting down...")
        
        self.stop()
    
    def stop(self) -> None:
        """Stop the monitoring application."""
        self.running = False
        self.shutdown_event.set()
    
    def _shutdown(self) -> None:
        """Perform cleanup during shutdown."""
        if self.logger:
            self.logger.log_shutdown()
            self.logger.info("Shutting down PingThis...")
        
        # Wait for monitor threads to finish (with timeout)
        for url, thread in self.monitor_threads.items():
            if thread.is_alive():
                if self.logger:
                    self.logger.debug(f"Waiting for monitor thread to finish", url)
                thread.join(timeout=5.0)
        
        # Close ping checker
        if self.ping_checker:
            self.ping_checker.close()
        
        if self.health_checker:
            self.health_checker.close()
        
        if self.logger:
            self.logger.info("PingThis shutdown complete")
    
    def get_status_summary(self) -> Dict:
        """
        Get a summary of current monitoring status.
        
        Returns:
            Dict with summary information
        """
        if not self.state_manager:
            return {"error": "State manager not initialized"}
        
        summary = self.state_manager.get_summary()
        statuses = self.state_manager.get_all_statuses()
        
        return {
            "summary": summary,
            "urls": {url: {
                "state": status.state.value,
                "last_check": status.last_check.isoformat() if status.last_check else None,
                "consecutive_failures": status.consecutive_failures,
                "consecutive_successes": status.consecutive_successes,
                "total_checks": status.total_checks,
                "average_response_time": status.average_response_time
            } for url, status in statuses.items()}
        }
    
    def send_summary_report(self) -> bool:
        """
        Send a summary report email.
        
        Returns:
            True if report was sent successfully, False otherwise
        """
        if not self.state_manager or not self.email_notifier:
            return False
        
        try:
            all_statuses = list(self.state_manager.get_all_statuses().values())
            return self.email_notifier.send_summary_report(all_statuses)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to send summary report: {e}", exc_info=True)
            return False


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="PingThis - Website Monitoring System")
    parser.add_argument(
        "--config", 
        default="config/monitoring_config.yaml",
        help="Path to configuration file (default: config/monitoring_config.yaml)"
    )
    parser.add_argument(
        "--test-config", 
        action="store_true",
        help="Test configuration and exit"
    )
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Show current status and exit"
    )
    parser.add_argument(
        "--send-report", 
        action="store_true",
        help="Send summary report email and exit"
    )
    
    args = parser.parse_args()
    
    try:
        app = PingThisApplication(args.config)
        
        if args.test_config:
            # Test configuration
            if app.initialize():
                print("✅ Configuration is valid")
                print(f"📧 Email connection test: {'✅ Success' if app.email_notifier.test_email_connection() else '❌ Failed'}")
                print(f"🔗 Monitoring {len(app.config.monitors)} URLs")
                sys.exit(0)
            else:
                print("❌ Configuration test failed")
                sys.exit(1)
        
        elif args.status:
            # Show current status
            if app.initialize():
                summary = app.get_status_summary()
                print("PingThis Status Summary:")
                print(f"Total URLs: {summary['summary']['total']}")
                print(f"Up: {summary['summary']['up']}")
                print(f"Down: {summary['summary']['down']}")
                print(f"Unknown: {summary['summary']['unknown']}")
                sys.exit(0)
            else:
                print("Failed to initialize application")
                sys.exit(1)
        
        elif args.send_report:
            # Send summary report
            if app.initialize():
                if app.send_summary_report():
                    print("✅ Summary report sent successfully")
                    sys.exit(0)
                else:
                    print("❌ Failed to send summary report")
                    sys.exit(1)
            else:
                print("Failed to initialize application")
                sys.exit(1)
        
        else:
            # Normal operation - start monitoring
            app.start()
    
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
