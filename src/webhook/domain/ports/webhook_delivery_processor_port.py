from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
from src.webhook.application.dto.webhook_delivery_dto import WebhookDeliveryDTO

class WebhookDeliveryProcessorPort(ABC):
    @abstractmethod
    def get_pending(self, limit: int = 50) -> List[WebhookDeliveryDTO]:
        raise NotImplementedError

    @abstractmethod
    def mark_as_sent(self, delivery_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_as_failed(self, delivery_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_retry(self, delivery_id: int, attempts: int, next_attempt_at: datetime) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_for_retry(self, delivery_id: int) -> None:
        raise NotImplementedError