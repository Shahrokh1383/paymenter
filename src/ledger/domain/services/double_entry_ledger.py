from typing import Optional
from src.common.domain.value_objects.money import Money
from src.common.domain.exceptions import InvalidTransactionStateError
from src.ledger.domain.entities.account import Account
from src.ledger.domain.entities.transaction import Transaction

class DoubleEntryLedger:
    """Pure domain service for orchestrating double-entry fund movements."""

    @staticmethod
    def hold_funds(from_acc: Account, to_acc: Account, amount: Money, merchant_id: Optional[int], user_email: Optional[str]) -> Transaction:
        from_acc.withdraw(amount)
        return Transaction.create_pending(
            from_account_id=from_acc.id,
            to_account_id=to_acc.id,
            amount=amount,
            merchant_id=merchant_id,
            user_email=user_email
        )

    @staticmethod
    def complete_funds(txn: Transaction, to_acc: Account) -> None:
        """Finalizes a Pending transaction and deposits funds into the destination account."""
        txn.mark_as_success()
        to_acc.deposit(txn.amount)

    @staticmethod
    def fail_and_refund(txn: Transaction, from_acc: Account, to_acc: Account) -> None:
        """
        Fails a Pending transaction (refunding the sender) 
        or Refunds a Successful transaction (reversing both legs).
        """
        if txn.status == 'Pending':
            txn.mark_as_failed()
            from_acc.deposit(txn.amount)  # Refund the sender
        elif txn.status == 'Success':
            txn.mark_as_refunded()
            from_acc.deposit(txn.amount)  # Refund the sender
            to_acc.withdraw(txn.amount)   # Reverse the deposit
        else:
            raise InvalidTransactionStateError(f"Cannot refund/fail transaction with status: {txn.status}")