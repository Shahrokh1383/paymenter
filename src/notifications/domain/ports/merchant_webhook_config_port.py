from abc import ABC, abstractmethod
from typing import Optional
from src.identity.application.dto.webhook_config_dto import WebhookConfigDTO

class MerchantWebhookConfigPort(ABC):
    """ACL Port for fetching merchant webhook configuration."""
    @abstractmethod
    def get_config(self, merchant_id: int) -> Optional[WebhookConfigDTO]:
        raise NotImplementedError