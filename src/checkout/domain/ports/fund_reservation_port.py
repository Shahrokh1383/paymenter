from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

class FundReservationPort(ABC):
    """
    Anti-Corruption Layer Port for reserving funds in the Ledger.
    Checkout context uses this to hold funds without knowing Ledger's internals.
    """
    
    @abstractmethod
    def hold_funds(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: Decimal,
        currency_code: str,
        merchant_id: Optional[int] = None,
        user_email: Optional[str] = None
    ) -> int:
        """
        Requests the Ledger to hold funds.
        Returns the transaction_id of the newly created Pending transaction.
        """
        raise NotImplementedError