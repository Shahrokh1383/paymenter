from dataclasses import dataclass
from typing import Optional

@dataclass
class CreateAccountCommand:
    user_id: Optional[int]
    merchant_id: Optional[int]
    currency_code: str