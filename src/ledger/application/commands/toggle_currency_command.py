from dataclasses import dataclass

@dataclass(frozen=True)
class ToggleCurrencyCommand:
    currency_id: int