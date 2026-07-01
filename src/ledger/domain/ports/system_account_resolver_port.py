from abc import ABC, abstractmethod
from src.ledger.domain.entities.account import Account
from src.common.domain.value_objects.currency_code import CurrencyCode

class SystemAccountResolverPort(ABC):
    """Port for resolving internal system accounts required for ledger balancing."""
    
    @abstractmethod
    def get_escrow_account(self, currency: CurrencyCode) -> Account:
        """
        Retrieves the system Escrow account for a specific currency.
        """
        pass