from dataclasses import dataclass
from src.common.domain.value_objects.email_address import EmailAddress
from src.common.domain.value_objects.money import Money
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.value_objects.otp_code import OtpCode

@dataclass(frozen=True)
class OtpRequestedEvent:
    session_token: SessionToken
    registered_email: EmailAddress
    otp_code: OtpCode
    merchant_name: str
    amount: Money