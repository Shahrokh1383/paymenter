from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class TopupAccountCommand:
    account_id: str
    amount: Decimal