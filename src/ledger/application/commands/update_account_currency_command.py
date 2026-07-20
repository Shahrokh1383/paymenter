from dataclasses import dataclass

@dataclass(frozen=True)
class UpdateAccountCurrencyCommand:
    account_id: str
    currency_code: str