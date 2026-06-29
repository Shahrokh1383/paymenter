from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.exceptions import AccountNotFoundError, InvalidTransactionStateError
from src.ledger.domain.repositories import AccountRepository, TransactionRepository
from src.ledger.domain.services.double_entry_ledger import DoubleEntryLedger
from src.ledger.domain.events.transaction_events import TransactionFailedEvent, TransactionRefundedEvent
from src.ledger.application.commands.fail_and_refund_command import FailAndRefundCommand

class FailAndRefundHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, txn_repo: TransactionRepository, event_bus: EventBus):
        self._uow = uow
        self._account_repo = account_repo
        self._txn_repo = txn_repo
        self._event_bus = event_bus

    def handle(self, command: FailAndRefundCommand) -> None:
        event_to_publish = None
        
        with self._uow:
            txn = self._txn_repo.get_by_id(command.transaction_id)
            if not txn:
                raise InvalidTransactionStateError("Transaction not found.")
                
            from_acc = self._account_repo.get_by_id(txn.from_account_id)
            to_acc = self._account_repo.get_by_id(txn.to_account_id)
            
            if not from_acc or not to_acc:
                raise AccountNotFoundError("Associated accounts not found.")

            DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc)
            
            self._txn_repo.update(txn)
            self._account_repo.update(from_acc)
            self._account_repo.update(to_acc)
            self._uow.commit()

            if txn.status == 'Failed':
                event_to_publish = TransactionFailedEvent(
                    transaction_id=txn.id, user_email=txn.user_email,
                    amount=txn.amount, merchant_id=txn.merchant_id
                )
            elif txn.status == 'Refunded':
                event_to_publish = TransactionRefundedEvent(
                    transaction_id=txn.id, user_email=txn.user_email,
                    amount=txn.amount, merchant_id=txn.merchant_id
                )
                
        if event_to_publish:
            self._event_bus.publish(event_to_publish)