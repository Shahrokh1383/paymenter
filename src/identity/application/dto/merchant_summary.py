from dataclasses import dataclass

@dataclass(frozen=True)
class MerchantSummaryDTO:
    id: int
    name: str
    api_key: str
    is_active: bool
    settlement_balance: str