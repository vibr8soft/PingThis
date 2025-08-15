"""
Website ping/health check functionality for PingThis application.

This module handles HTTP requests to monitor website availability and performance.
"""

import requests
import time
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config.config_manager import MonitorConfig
from ..utils.logger import get_logger


@dataclass
class PingResult:
    """Result of a ping/health check operation."""
    url: str
    success: bool
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PingChecker:
    """Handles website health checks and ping operations."""
    
    def __init__(self):
        """Initialize the PingChecker."""
        self.logger = get_logger()
        self.session = requests.Session()
        
        # Configure session with reasonable defaults
        self.session.headers.update({
            'User-Agent': 'PingThis/1.0.0 (Website Monitor)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def ping_url(self, monitor_config: MonitorConfig) -> PingResult:
        """
        Perform a health check on a single URL.
        
        Args:
            monitor_config: Configuration for the monitor
            
        Returns:
            PingResult: Result of the ping operation
        """
        url = monitor_config.url
        start_time = time.time()
        
        try:
            self.logger.debug(f"Starting ping check", url)
            
            # Perform the HTTP request
            response = self.session.get(
                url,
                timeout=monitor_config.timeout,
                allow_redirects=True,
                verify=True  # Verify SSL certificates
            )
            
            response_time = time.time() - start_time
            
            # Check if status code is acceptable
            is_success = response.status_code in monitor_config.expected_status_codes
            
            result = PingResult(
                url=url,
                success=is_success,
                status_code=response.status_code,
                response_time=response_time,
                error_message=None if is_success else f"Unexpected status code: {response.status_code}"
            )
            
            # Log the result
            self.logger.log_ping_result(
                url=url,
                success=is_success,
                response_time=response_time,
                status_code=response.status_code,
                error_message=result.error_message
            )
            
            return result
            
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            error_msg = f"Request timeout after {monitor_config.timeout}s"
            
            result = PingResult(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            self.logger.log_ping_result(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            return result
            
        except requests.exceptions.ConnectionError as e:
            response_time = time.time() - start_time
            error_msg = f"Connection error: {str(e)}"
            
            result = PingResult(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            self.logger.log_ping_result(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            return result
            
        except requests.exceptions.SSLError as e:
            response_time = time.time() - start_time
            error_msg = f"SSL error: {str(e)}"
            
            result = PingResult(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            self.logger.log_ping_result(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            return result
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            error_msg = f"Request error: {str(e)}"
            
            result = PingResult(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            self.logger.log_ping_result(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"Unexpected error: {str(e)}"
            
            result = PingResult(
                url=url,
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
            
            self.logger.error(f"Unexpected error during ping: {str(e)}", url, exc_info=True)
            
            return result
    
    def ping_multiple_urls(self, monitor_configs: list[MonitorConfig]) -> Dict[str, PingResult]:
        """
        Perform health checks on multiple URLs.
        
        Args:
            monitor_configs: List of monitor configurations
            
        Returns:
            Dict mapping URL to PingResult
        """
        results = {}
        
        for config in monitor_configs:
            try:
                result = self.ping_url(config)
                results[config.url] = result
            except Exception as e:
                self.logger.error(f"Failed to ping URL: {str(e)}", config.url, exc_info=True)
                results[config.url] = PingResult(
                    url=config.url,
                    success=False,
                    error_message=f"Failed to ping: {str(e)}"
                )
        
        return results
    
    def close(self) -> None:
        """Clean up resources."""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class HealthChecker:
    """Advanced health checker with additional features."""
    
    def __init__(self):
        """Initialize the HealthChecker."""
        self.ping_checker = PingChecker()
        self.logger = get_logger()
    
    def is_url_healthy(self, monitor_config: MonitorConfig, consecutive_failures: int = 0) -> Tuple[bool, PingResult]:
        """
        Check if a URL is healthy with enhanced logic.
        
        Args:
            monitor_config: Configuration for the monitor
            consecutive_failures: Number of consecutive failures so far
            
        Returns:
            Tuple of (is_healthy, PingResult)
        """
        result = self.ping_checker.ping_url(monitor_config)
        
        # URL is healthy if the ping was successful
        is_healthy = result.success
        
        # Additional checks could be added here:
        # - Response time thresholds
        # - Content validation
        # - Header checks
        
        if result.response_time and result.response_time > monitor_config.timeout * 0.8:
            self.logger.warning(
                f"Slow response time: {result.response_time:.3f}s "
                f"(timeout threshold: {monitor_config.timeout}s)",
                monitor_config.url
            )
        
        return is_healthy, result
    
    def perform_deep_check(self, monitor_config: MonitorConfig) -> Dict[str, Any]:
        """
        Perform a deep health check with additional metrics.
        
        Args:
            monitor_config: Configuration for the monitor
            
        Returns:
            Dict with detailed health information
        """
        # Perform multiple pings to get average response time
        results = []
        for _ in range(3):
            result = self.ping_checker.ping_url(monitor_config)
            results.append(result)
            time.sleep(0.5)  # Small delay between pings
        
        # Calculate metrics
        successful_pings = [r for r in results if r.success]
        failed_pings = [r for r in results if not r.success]
        
        avg_response_time = None
        if successful_pings:
            response_times = [r.response_time for r in successful_pings if r.response_time]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return {
            'url': monitor_config.url,
            'total_pings': len(results),
            'successful_pings': len(successful_pings),
            'failed_pings': len(failed_pings),
            'success_rate': len(successful_pings) / len(results),
            'average_response_time': avg_response_time,
            'last_result': results[-1] if results else None,
            'all_results': results
        }
    
    def close(self) -> None:
        """Clean up resources."""
        self.ping_checker.close()
