from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ConfigureWebhookCommand:
    merchant_id: int
    webhook_url: Optional[str]
    webhook_enabled: bool

@dataclass(frozen=True)
class GenerateWebhookSecretCommand:
    merchant_id: int