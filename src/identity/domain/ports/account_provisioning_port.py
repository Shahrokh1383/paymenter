from abc import ABC, abstractmethod
from typing import Optional

class AccountProvisioningPort(ABC):
    @abstractmethod
    def create_default_account(self, user_id: Optional[int], currency_id: int) -> int:
        raise NotImplementedError