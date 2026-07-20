from abc import ABC, abstractmethod
from typing import List
from src.notifications.application.dto.webhook_delivery_dto import WebhookDeliveryDTO

class WebhookDeliveryQueryPort(ABC):
    """Port for querying webhook deliveries for the Admin UI."""
    @abstractmethod
    def get_all(self) -> List[WebhookDeliveryDTO]:
        raise NotImplementedError