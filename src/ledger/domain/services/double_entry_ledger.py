from typing import Optional
from src.common.domain.value_objects.money import Money
from src.common.domain.exceptions import InvalidTransactionStateError
from src.ledger.domain.entities.account import Account
from src.ledger.domain.entities.transaction import Transaction

class DoubleEntryLedger:
    """Pure domain service for orchestrating double-entry fund movements."""

    @staticmethod
    def hold_funds(from_acc: Account, to_acc: Account, amount: Money, escrow_acc: Account, merchant_id: Optional[int], user_email: Optional[str]) -> Transaction:
        from_acc.withdraw(amount)
        from_acc.increase_holds(amount)
        
        if escrow_acc is not from_acc:
            escrow_acc.deposit(amount)
            
        return Transaction.create_pending(
            from_account_id=from_acc.id,
            to_account_id=to_acc.id,
            amount=amount,
            merchant_id=merchant_id,
            user_email=user_email
        )

    @staticmethod
    def complete_funds(txn: Transaction, from_acc: Account, to_acc: Account, escrow_acc: Account) -> None:
        """Finalizes a Pending transaction, moving funds from Escrow to the destination account."""
        txn.mark_as_success()
        
        from_acc.decrease_holds(txn.amount)
        
        if escrow_acc is not to_acc:
            escrow_acc.withdraw(txn.amount)
            to_acc.deposit(txn.amount)

    @staticmethod
    def fail_and_refund(txn: Transaction, from_acc: Account, to_acc: Account, escrow_acc: Account) -> None:
        """
        Fails a Pending transaction (refunding from Escrow to sender) 
        or Refunds a Successful transaction (reversing both legs).
        """
        if txn.status == 'Pending':
            txn.mark_as_failed()
            from_acc.decrease_holds(txn.amount)
            
            if escrow_acc is not from_acc:
                escrow_acc.withdraw(txn.amount)
                from_acc.deposit(txn.amount)
                
        elif txn.status == 'Success':
            txn.mark_as_refunded()
            from_acc.deposit(txn.amount)
            to_acc.apply_system_reversal(txn.amount) 
            # Note: Escrow is untouched here because it was zeroed out during complete_funds
        else:
            raise InvalidTransactionStateError(f"Cannot refund/fail transaction with status: {txn.status}")