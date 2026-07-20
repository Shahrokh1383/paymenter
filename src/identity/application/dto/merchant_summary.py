from dataclasses import dataclass
from typing import Optional

@dataclass
class MerchantSummaryDTO:
    id: int
    name: str
    api_key: str
    is_active: bool
    webhook_url: Optional[str] = None
    webhook_enabled: bool = False