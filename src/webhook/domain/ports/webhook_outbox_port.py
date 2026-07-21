from abc import ABC, abstractmethod

class WebhookOutboxPort(ABC):
    @abstractmethod
    def add(self, merchant_id: int, event_type: str, payload: str, signature: str) -> None:
        raise NotImplementedError