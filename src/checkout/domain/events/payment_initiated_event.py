from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class PaymentInitiatedEvent:
    session_token: str
    user_email: str
    merchant_name: str
    amount: Decimal
    currency_code: str