from dataclasses import dataclass
from src.common.domain.value_objects.currency_code import CurrencyCode

@dataclass(frozen=True)
class CurrencySummaryDTO:
    id: int
    name: str
    code: CurrencyCode
    is_active: bool