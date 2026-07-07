from dataclasses import dataclass

@dataclass(frozen=True)
class OnboardMerchantCommand:
    name: str

@dataclass(frozen=True)
class ToggleMerchantCommand:
    merchant_id: int