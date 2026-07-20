from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class TransactionListItem:
    """Read Model DTO for the UI list view. Prevents N+1 queries."""
    id: str
    amount: Decimal
    currency_code: str
    status: str
    created_at: datetime
    user_email: Optional[str]
    from_account_number: str
    to_account_number: str