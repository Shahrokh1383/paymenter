from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class UserSummaryDTO:
    user_id: int
    name: str
    phone_email: str
    account_id: Optional[int]
    account_number: Optional[str]
    card_number: Optional[str]
    balance: Optional[str]
    currency_code: Optional[str]