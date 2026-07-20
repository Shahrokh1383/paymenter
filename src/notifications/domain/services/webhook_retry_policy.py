from datetime import datetime, timedelta, timezone
from typing import Optional

class WebhookRetryPolicy:
    """Pure domain logic for calculating webhook retry intervals."""
    
    MAX_ATTEMPTS = 5
    INTERVALS = [
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=30),
        timedelta(hours=1),
        timedelta(hours=2),
    ]

    @staticmethod
    def calculate_next_attempt(current_attempts: int) -> Optional[datetime]:
        if current_attempts >= WebhookRetryPolicy.MAX_ATTEMPTS:
            return None
        
        index = min(current_attempts, len(WebhookRetryPolicy.INTERVALS) - 1)
        # Use timezone-aware UTC datetime
        return datetime.now(timezone.utc) + WebhookRetryPolicy.INTERVALS[index]