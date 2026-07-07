from dataclasses import dataclass
from src.common.domain.value_objects.money import Money

@dataclass(frozen=True)
class AccountOwnerProfile:
    email: str
    balance: Money