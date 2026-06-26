from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.email_address import EmailAddress
from src.common.domain.exceptions import DomainException
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.value_objects.otp_code import OtpCode
from src.checkout.domain.value_objects.callback_url import CallbackUrl

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
    otp_code: OtpCode
    status: str = 'Initiated'
    transaction_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def authorize(self, input_otp: str) -> None:
        """Validates OTP and transitions state to Authorized."""
        if self.status != 'Initiated':
            raise PaymentSessionStateError(f"Cannot authorize session in '{self.status}' state.")
        
        if not self.otp_code.verify(input_otp):
            raise InvalidOtpError("Invalid OTP code provided.")
            
        self.status = 'Authorized'
        
    def attach_transaction(self, transaction_id: int) -> None:
        """Links the underlying Ledger transaction to this session."""
        if self.status != 'Authorized':
            raise PaymentSessionStateError("Can only attach transaction to an Authorized session.")
        self.transaction_id = transaction_id

    def mark_as_failed(self) -> None:
        if self.status not in ['Initiated', 'Authorized']:
             raise PaymentSessionStateError(f"Cannot fail session in '{self.status}' state.")
        self.status = 'Failed'