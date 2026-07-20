from dataclasses import dataclass
from typing import Optional
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.value_objects.webhook_url import WebhookUrl

@dataclass
class Merchant:
    id: int
    name: str
    api_key: ApiKey
    is_active: bool
    webhook_url: Optional[WebhookUrl] = None
    webhook_secret: Optional[str] = None
    webhook_enabled: bool = False
    
    def toggle(self) -> None: 
        self.is_active = not self.is_active

    def configure_webhook(self, url: Optional[str], enabled: bool) -> None:
        """Protects the invariant: Webhook cannot be enabled without a valid URL."""
        if enabled and not url:
            raise ValueError("Cannot enable webhook without providing a valid URL.")
        
        self.webhook_url = WebhookUrl(url) if url else None
        self.webhook_enabled = enabled if self.webhook_url else False

    def set_webhook_secret(self, secret: str) -> None:
        """Sets the generated secret. In a real system, this would be hashed before storage."""
        if not secret or len(secret) < 20:
            raise ValueError("Webhook secret must be at least 20 characters long.")
        self.webhook_secret = secret