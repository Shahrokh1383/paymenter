from dataclasses import dataclass

@dataclass(frozen=True)
class UpdateAccountCurrencyCommand:
    account_id: int
    currency_id: int