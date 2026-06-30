from abc import ABC, abstractmethod
from typing import Optional

class AccountOwnerResolverPort(ABC):
    """
    Anti-Corruption Layer (ACL) Port.
    Resolves the registered Identity email for a given Ledger Account ID.
    """
    @abstractmethod
    def get_email_by_account_id(self, account_id: int) -> Optional[str]:
        raise NotImplementedError