from abc import ABC, abstractmethod

class NotificationDispatcher(ABC):
    @abstractmethod
    def send_receipt(self, to_email: str, status: str, amount: float, currency_code: str, merchant_name: str) -> None:
        raise NotImplementedError