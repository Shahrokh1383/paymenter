from dataclasses import dataclass
from src.common.domain.value_objects.currency_code import CurrencyCode

@dataclass(frozen=True)
class CurrencyCreatedEvent:
    currency_id: str
    name: str
    code: CurrencyCode

@dataclass(frozen=True)
class CurrencyActivatedEvent:
    currency_id: str
    code: CurrencyCode

@dataclass(frozen=True)
class CurrencyDeactivatedEvent:
    currency_id: str
    code: CurrencyCode