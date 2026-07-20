from abc import ABC, abstractmethod

class WebhookOutboxPort(ABC):
    """Port for persisting webhook messages to the outbox."""
    @abstractmethod
    def add(self, merchant_id: int, event_type: str, payload: str, signature: str) -> None:
        raise NotImplementedError