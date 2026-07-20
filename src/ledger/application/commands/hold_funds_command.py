from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class HoldFundsCommand:
    from_account_id: str
    to_account_id: str
    amount: Decimal
    merchant_id: Optional[int] = None
    user_email: Optional[str] = None