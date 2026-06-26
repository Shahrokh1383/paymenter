from abc import ABC, abstractmethod

class AccountProvisioningPort(ABC):
    @abstractmethod
    def create_default_account(self, user_id: int, currency_id: int) -> int:
        raise NotImplementedError