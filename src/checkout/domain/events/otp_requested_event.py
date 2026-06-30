from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class OtpRequestedEvent:
    session_token: str
    registered_email: str
    otp_code: str
    merchant_name: str
    amount: Decimal
    currency_code: str