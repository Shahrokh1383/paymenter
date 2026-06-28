from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class AccountSummary:
    id: int
    user_id: int
    user_name: str
    currency_id: int
    currency_code: str
    account_number: str
    balance: Decimal