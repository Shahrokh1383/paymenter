from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class EscrowAccountSummary:
    id: str
    currency_id: str
    currency_code: str
    account_number: str
    balance: Decimal