from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass(frozen=True)
class TransactionStatus:
    """Immutable DTO representing the status of a transaction from the Ledger."""
    transaction_id: int
    status: str
    amount: float
    currency_code: str

class TransactionVerificationPort(ABC):
    """
    Anti-Corruption Layer Port for verifying transaction status in the Ledger.
    """
    
    @abstractmethod
    def get_transaction_status(self, transaction_id: int) -> Optional[TransactionStatus]:
        """
        Queries the Ledger for the current status of a transaction.
        Returns None if the transaction does not exist or does not belong to the requesting merchant.
        """
        raise NotImplementedError