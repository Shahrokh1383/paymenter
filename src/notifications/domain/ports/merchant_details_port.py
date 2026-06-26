from abc import ABC, abstractmethod
from typing import Optional

class MerchantDetailsPort(ABC):
    """ACL Port to fetch merchant data without coupling to the Ledger/Identity DB schema."""
    @abstractmethod
    def get_merchant_name(self, merchant_id: int) -> Optional[str]:
        raise NotImplementedError