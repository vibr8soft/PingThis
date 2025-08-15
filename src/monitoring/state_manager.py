"""
State management for PingThis application.

This module tracks the up/down state of monitored URLs and manages
alert notifications to prevent spam.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from .ping_checker import PingResult
from ..utils.logger import get_logger


class UrlState(Enum):
    """Possible states for a monitored URL."""
    UP = "UP"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class UrlStatus:
    """Status information for a monitored URL."""
    url: str
    state: UrlState
    last_check: datetime
    last_state_change: datetime
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_checks: int = 0
    total_failures: int = 0
    alert_sent: bool = False
    recovery_alert_sent: bool = False
    last_error_message: Optional[str] = None
    average_response_time: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['last_check'] = self.last_check.isoformat() if self.last_check else None
        data['last_state_change'] = self.last_state_change.isoformat() if self.last_state_change else None
        data['state'] = self.state.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UrlStatus':
        """Create from dictionary (JSON deserialization)."""
        # Convert ISO strings back to datetime objects
        if data.get('last_check'):
            data['last_check'] = datetime.fromisoformat(data['last_check'])
        if data.get('last_state_change'):
            data['last_state_change'] = datetime.fromisoformat(data['last_state_change'])
        if data.get('state'):
            data['state'] = UrlState(data['state'])
        
        return cls(**data)


class StateManager:
    """Manages the state of monitored URLs and alert notifications."""
    
    def __init__(self, state_file: str = "logs/pingthis_state.json"):
        """
        Initialize the StateManager.
        
        Args:
            state_file: Path to the state persistence file
        """
        self.state_file = state_file
        self.url_states: Dict[str, UrlStatus] = {}
        self.logger = get_logger()
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from the persistence file."""
        if not os.path.exists(self.state_file):
            self.logger.debug(f"State file does not exist: {self.state_file}")
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            for url, state_data in data.items():
                try:
                    self.url_states[url] = UrlStatus.from_dict(state_data)
                except Exception as e:
                    self.logger.error(f"Failed to load state for URL {url}: {e}")
            
            self.logger.info(f"Loaded state for {len(self.url_states)} URLs")
            
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to load state file {self.state_file}: {e}")
    
    def _save_state(self) -> None:
        """Save current state to the persistence file."""
        try:
            # Ensure the directory exists
            state_dir = os.path.dirname(self.state_file)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)
            
            # Convert to serializable format
            data = {url: status.to_dict() for url, status in self.url_states.items()}
            
            # Write to file
            with open(self.state_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved state for {len(self.url_states)} URLs")
            
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to save state file {self.state_file}: {e}")
    
    def update_url_status(self, ping_result: PingResult) -> Tuple[bool, bool]:
        """
        Update the status of a URL based on ping result.
        
        Args:
            ping_result: Result of the ping operation
            
        Returns:
            Tuple of (state_changed, should_send_alert)
        """
        url = ping_result.url
        current_time = ping_result.timestamp
        
        # Get existing status or create new one
        if url not in self.url_states:
            self.url_states[url] = UrlStatus(
                url=url,
                state=UrlState.UNKNOWN,
                last_check=current_time,
                last_state_change=current_time
            )
        
        status = self.url_states[url]
        old_state = status.state
        
        # Update basic stats
        status.last_check = current_time
        status.total_checks += 1
        
        # Determine new state
        new_state = UrlState.UP if ping_result.success else UrlState.DOWN
        
        # Update consecutive counters
        if ping_result.success:
            status.consecutive_successes += 1
            status.consecutive_failures = 0
        else:
            status.consecutive_failures += 1
            status.consecutive_successes = 0
            status.total_failures += 1
            status.last_error_message = ping_result.error_message
        
        # Update response time average (simple moving average)
        if ping_result.response_time is not None:
            if status.average_response_time is None:
                status.average_response_time = ping_result.response_time
            else:
                # Simple exponential moving average with alpha = 0.3
                alpha = 0.3
                status.average_response_time = (
                    alpha * ping_result.response_time + 
                    (1 - alpha) * status.average_response_time
                )
        
        # Check for state change
        state_changed = old_state != new_state
        
        if state_changed:
            status.state = new_state
            status.last_state_change = current_time
            self.logger.log_state_change(url, old_state.value, new_state.value)
            
            # Reset alert flags when state changes
            if new_state == UrlState.DOWN:
                status.alert_sent = False
                status.recovery_alert_sent = False
            elif new_state == UrlState.UP:
                status.recovery_alert_sent = False
        
        # Determine if we should send an alert
        should_send_alert = self._should_send_alert(status, old_state, state_changed)
        
        # Save state to persistence
        self._save_state()
        
        return state_changed, should_send_alert
    
    def _should_send_alert(self, status: UrlStatus, old_state: UrlState, state_changed: bool) -> bool:
        """
        Determine if an alert should be sent based on current status.
        
        Args:
            status: Current URL status
            old_state: Previous state
            state_changed: Whether the state changed
            
        Returns:
            True if an alert should be sent
        """
        # Send DOWN alert if:
        # 1. State changed from UP to DOWN
        # 2. Previous state was UP (confirmed working before)
        # 3. Haven't sent a DOWN alert yet for this downtime
        if (status.state == UrlState.DOWN and 
            state_changed and 
            old_state == UrlState.UP and 
            not status.alert_sent):
            status.alert_sent = True
            return True
        
        # Send RECOVERY alert if:
        # 1. State changed from DOWN to UP
        # 2. We had previously sent a DOWN alert
        # 3. Haven't sent a recovery alert yet for this recovery
        if (status.state == UrlState.UP and 
            state_changed and 
            old_state == UrlState.DOWN and 
            status.alert_sent and 
            not status.recovery_alert_sent):
            status.recovery_alert_sent = True
            return True
        
        return False
    
    def get_url_status(self, url: str) -> Optional[UrlStatus]:
        """
        Get the current status of a URL.
        
        Args:
            url: URL to get status for
            
        Returns:
            UrlStatus if found, None otherwise
        """
        return self.url_states.get(url)
    
    def get_all_statuses(self) -> Dict[str, UrlStatus]:
        """Get all URL statuses."""
        return self.url_states.copy()
    
    def get_down_urls(self) -> List[UrlStatus]:
        """Get all URLs that are currently down."""
        return [status for status in self.url_states.values() 
                if status.state == UrlState.DOWN]
    
    def get_up_urls(self) -> List[UrlStatus]:
        """Get all URLs that are currently up."""
        return [status for status in self.url_states.values() 
                if status.state == UrlState.UP]
    
    def get_unknown_urls(self) -> List[UrlStatus]:
        """Get all URLs with unknown status."""
        return [status for status in self.url_states.values() 
                if status.state == UrlState.UNKNOWN]
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get a summary of all URL states.
        
        Returns:
            Dict with counts for each state
        """
        summary = {
            'total': len(self.url_states),
            'up': 0,
            'down': 0,
            'unknown': 0
        }
        
        for status in self.url_states.values():
            if status.state == UrlState.UP:
                summary['up'] += 1
            elif status.state == UrlState.DOWN:
                summary['down'] += 1
            else:
                summary['unknown'] += 1
        
        return summary
    
    def cleanup_old_state(self, max_age_days: int = 30) -> int:
        """
        Clean up state for URLs that haven't been checked recently.
        
        Args:
            max_age_days: Maximum age in days for keeping state
            
        Returns:
            Number of URLs cleaned up
        """
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        urls_to_remove = []
        
        for url, status in self.url_states.items():
            if status.last_check < cutoff_time:
                urls_to_remove.append(url)
        
        for url in urls_to_remove:
            del self.url_states[url]
            self.logger.info(f"Cleaned up old state for URL: {url}")
        
        if urls_to_remove:
            self._save_state()
        
        return len(urls_to_remove)
    
    def reset_alerts_for_url(self, url: str) -> bool:
        """
        Reset alert flags for a specific URL.
        
        Args:
            url: URL to reset alerts for
            
        Returns:
            True if URL was found and reset, False otherwise
        """
        if url in self.url_states:
            status = self.url_states[url]
            status.alert_sent = False
            status.recovery_alert_sent = False
            self._save_state()
            self.logger.info(f"Reset alert flags for URL: {url}")
            return True
        return False
    
    def force_state_change(self, url: str, new_state: UrlState) -> bool:
        """
        Force a state change for a URL (for testing or manual intervention).
        
        Args:
            url: URL to change state for
            new_state: New state to set
            
        Returns:
            True if URL was found and state changed, False otherwise
        """
        if url in self.url_states:
            old_state = self.url_states[url].state
            self.url_states[url].state = new_state
            self.url_states[url].last_state_change = datetime.now()
            self._save_state()
            
            self.logger.warning(f"Manually forced state change from {old_state.value} to {new_state.value}", url)
            return True
        return False
