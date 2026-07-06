from dataclasses import dataclass
from src.identity.domain.value_objects.api_key import ApiKey

@dataclass(frozen=True)
class MerchantOnboardedEvent:
    merchant_id: int
    name: str
    api_key: ApiKey

@dataclass(frozen=True)
class MerchantActivatedEvent:
    merchant_id: int

@dataclass(frozen=True)
class MerchantDeactivatedEvent:
    merchant_id: int