from dataclasses import dataclass

@dataclass(frozen=True)
class OnboardMerchantCommand:
    name: str

@dataclass(frozen=True)
class ToggleMerchantCommand:
    merchant_id: int

@dataclass(frozen=True)
class AddCurrencyCommand:
    name: str
    code: str

@dataclass(frozen=True)
class ToggleCurrencyCommand:
    currency_id: int