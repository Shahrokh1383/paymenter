from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class AccountSummary:
    id: str
    user_id: int
    user_name: str
    currency_id: str
    currency_code: str
    account_number: str
    balance: Decimal
    pending_holds: Decimal
    open_authorizations: int
    card_number: Optional[str] = None