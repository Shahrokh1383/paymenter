from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class InitiatePaymentCommand:
    merchant_id: int
    merchant_name: str
    amount: Decimal
    currency_code: str
    user_email: str
    callback_url: str