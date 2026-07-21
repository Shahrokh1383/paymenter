from abc import ABC, abstractmethod
from typing import List
from src.webhook.application.dto.webhook_delivery_dto import WebhookDeliveryDTO

class WebhookDeliveryQueryPort(ABC):
    @abstractmethod
    def get_all(self) -> List[WebhookDeliveryDTO]:
        raise NotImplementedError