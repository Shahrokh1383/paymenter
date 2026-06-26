from abc import ABC, abstractmethod

class TransactionRefundPort(ABC):
    """
    Anti-Corruption Layer Port for refunding or failing transactions in the Ledger.
    """
    
    @abstractmethod
    def refund_or_fail(self, transaction_id: int) -> None:
        """
        Requests the Ledger to either fail a Pending transaction (refunding the user)
        or refund a Successful transaction (reversing both legs).
        """
        raise NotImplementedError