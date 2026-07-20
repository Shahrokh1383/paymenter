from dataclasses import dataclass
from typing import Optional

@dataclass
class WebhookDeliveryDTO:
    id: int
    merchant_id: int
    event_type: str
    payload: str
    signature: str
    status: str
    attempts: int
    last_attempt_at: Optional[str]
    next_attempt_at: Optional[str]
    created_at: str