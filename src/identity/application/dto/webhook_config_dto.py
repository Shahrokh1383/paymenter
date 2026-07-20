from dataclasses import dataclass
from typing import Optional

@dataclass
class WebhookConfigDTO:
    webhook_url: Optional[str]
    webhook_secret: Optional[str]
    webhook_enabled: bool