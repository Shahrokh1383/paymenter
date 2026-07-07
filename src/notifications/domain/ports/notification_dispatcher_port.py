from abc import ABC, abstractmethod
from src.common.domain.value_objects.email_address import EmailAddress
from src.common.domain.value_objects.money import Money

class NotificationDispatcher(ABC):
    @abstractmethod
    def send_receipt(self, to_email: EmailAddress, status: str, amount: Money, merchant_name: str, remaining_balance: Money) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_otp(self, to_email: EmailAddress, otp_code: str, merchant_name: str, amount: Money) -> None:
        """Sends a One-Time Password (OTP) to the user for payment verification."""
        raise NotImplementedError