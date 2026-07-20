from abc import ABC, abstractmethod
from typing import Optional
from src.notifications.domain.value_objects.account_owner_profile import AccountOwnerProfile

class AccountOwnerResolverPort(ABC):
    @abstractmethod
    def get_email_by_account_id(self, account_id: str) -> Optional[str]:
        raise NotImplementedError

    @abstractmethod
    def resolve_profile_by_account_id(self, account_id: str) -> Optional[AccountOwnerProfile]:
        """Fetches email and current balance atomically."""
        raise NotImplementedError