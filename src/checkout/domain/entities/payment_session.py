from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.email_address import EmailAddress
from src.common.domain.exceptions import DomainException
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.value_objects.otp_code import OtpCode
from src.checkout.domain.value_objects.callback_url import CallbackUrl
from src.checkout.domain.value_objects.card_number import CardNumber

class PaymentSessionStateError(DomainException):
    pass

class InvalidOtpError(DomainException):
    pass

@dataclass
class PaymentSession:
    id: int
    token: SessionToken
    merchant_id: int
    merchant_name: str
    amount: Money
    user_email: EmailAddress
    callback_url: CallbackUrl
    status: str = 'Initiated'
    transaction_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    otp_code: Optional[OtpCode] = None
    otp_locked_card: Optional[str] = None
    otp_expires_at: Optional[datetime] = None

    def request_otp(self, card: CardNumber, otp: OtpCode, expires_at: datetime) -> None:
        """Binds an OTP to a specific card and sets expiration."""
        if self.status != 'Initiated':
            raise PaymentSessionStateError("Can only request OTP for an Initiated session.")
        
        self.otp_code = otp
        self.otp_locked_card = card.value
        self.otp_expires_at = expires_at

    def authorize(self, card: CardNumber, input_otp: str) -> None:
        """Validates Card match, Expiration, and OTP value."""
        if self.status != 'Initiated':
            raise PaymentSessionStateError(f"Cannot authorize session in '{self.status}' state.")
        
        if not self.otp_code or not self.otp_locked_card or not self.otp_expires_at:
            raise PaymentSessionStateError("OTP has not been requested for this session yet.")

        if self.otp_expires_at < datetime.utcnow():
            raise InvalidOtpError("OTP has expired. Please request a new one.")

        if card.value != self.otp_locked_card:
            raise DomainException("The provided card does not match the one used for OTP request.")

        if not self.otp_code.verify(input_otp):
            raise InvalidOtpError("Invalid OTP code provided.")
            
        self.status = 'Authorized'
        
    def attach_transaction(self, transaction_id: int) -> None:
        if self.status != 'Authorized':
            raise PaymentSessionStateError("Can only attach transaction to an Authorized session.")
        self.transaction_id = transaction_id

    def mark_as_failed(self) -> None:
        if self.status not in ['Initiated', 'Authorized']:
             raise PaymentSessionStateError(f"Cannot fail session in '{self.status}' state.")
        self.status = 'Failed'