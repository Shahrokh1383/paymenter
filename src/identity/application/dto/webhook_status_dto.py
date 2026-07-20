from dataclasses import dataclass
from typing import Optional

@dataclass
class WebhookStatusDTO:
    webhook_url: Optional[str]
    webhook_enabled: bool