from dataclasses import dataclass
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.domain.value_objects.account_number import AccountNumber

@dataclass(frozen=True)
class AccountCreatedEvent:
    account_id: int
    user_id: int
    account_number: AccountNumber
    currency_code: CurrencyCode