from abc import ABC, abstractmethod
from src.ledger.domain.entities.account import Account

class SystemAccountResolverPort(ABC):
    """Port for resolving internal system accounts required for ledger balancing."""
    
    @abstractmethod
    def get_escrow_account(self, currency_code: str) -> Account:
        """
        Retrieves the system Escrow account for a specific currency.
        Uses currency-specific escrow to maintain BR-2 (Currency Homogeneity) without hardcoding IDs.
        """
        pass