from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class EscrowAccountSummary:
    id: int
    currency_id: int
    currency_code: str
    account_number: str
    balance: Decimal