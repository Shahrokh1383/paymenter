from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.exceptions import AccountNotFoundError, InvalidTransactionStateError
from src.ledger.domain.repositories import AccountRepository, TransactionRepository
from src.ledger.domain.ports.system_account_resolver_port import SystemAccountResolverPort
from src.ledger.domain.services.double_entry_ledger import DoubleEntryLedger
from src.ledger.domain.events.transaction_events import TransactionCompletedEvent
from src.ledger.application.commands.complete_funds_command import CompleteFundsCommand

class CompleteFundsHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, txn_repo: TransactionRepository, event_bus: EventBus, system_account_resolver: SystemAccountResolverPort):
        self._uow = uow
        self._account_repo = account_repo
        self._txn_repo = txn_repo
        self._event_bus = event_bus
        self._system_account_resolver = system_account_resolver

    def handle(self, command: CompleteFundsCommand) -> None:
        with self._uow:
            txn = self._txn_repo.get_by_id(command.transaction_id)
            if not txn:
                raise InvalidTransactionStateError("Transaction not found.")
                
            from_acc = self._account_repo.get_by_id(txn.from_account_id)
            to_acc = self._account_repo.get_by_id(txn.to_account_id)
            if not from_acc or not to_acc:
                raise AccountNotFoundError("Associated accounts not found.")

            escrow_acc = self._system_account_resolver.get_escrow_account(txn.amount.currency)
            
            if from_acc.id == escrow_acc.id:
                from_acc = escrow_acc
            if to_acc.id == escrow_acc.id:
                to_acc = escrow_acc

            DoubleEntryLedger.complete_funds(txn, from_acc, to_acc, escrow_acc)
            
            self._txn_repo.update(txn)
            self._account_repo.update(from_acc)
            if to_acc is not from_acc:
                self._account_repo.update(to_acc)
            if escrow_acc is not from_acc and escrow_acc is not to_acc:
                self._account_repo.update(escrow_acc)

            event_to_publish = TransactionCompletedEvent(
                transaction_id=txn.id,
                payer_account_id=txn.from_account_id,
                amount=txn.amount,
                merchant_id=txn.merchant_id
            )
            
            # MOVED INSIDE UoW: Event handlers will now join this transaction
            self._event_bus.publish(event_to_publish)
            # Commit is handled automatically by __exit__