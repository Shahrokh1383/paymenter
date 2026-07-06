from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CardAssignedEvent:
    account_id: int
    user_id: Optional[int]
    merchant_id: Optional[int]
    card_number: str