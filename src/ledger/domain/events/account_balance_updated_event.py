from dataclasses import dataclass
from src.common.domain.value_objects.money import Money

@dataclass(frozen=True)
class AccountBalanceUpdatedEvent:
    account_id: int
    user_id: int
    new_balance: Money