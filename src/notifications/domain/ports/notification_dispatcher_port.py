from abc import ABC, abstractmethod

class NotificationDispatcher(ABC):
    @abstractmethod
    def send_receipt(self, to_email: str, status: str, amount: float, currency_code: str, merchant_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_otp(self, to_email: str, otp_code: str, merchant_name: str, amount: float, currency_code: str) -> None:
        """Sends a One-Time Password (OTP) to the user for payment verification."""
        raise NotImplementedError