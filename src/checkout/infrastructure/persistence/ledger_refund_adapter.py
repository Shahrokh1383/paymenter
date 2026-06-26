from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.checkout.domain.ports.transaction_refund_port import TransactionRefundPort
from src.ledger.application.commands.fail_and_refund_command import FailAndRefundCommand
from src.ledger.application.handlers.fail_and_refund_handler import FailAndRefundHandler
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_repository import SqliteTransactionRepository

class LedgerRefundAdapter(TransactionRefundPort):
    def __init__(self, uow: UnitOfWork, event_bus: EventBus):
        self._uow = uow
        self._event_bus = event_bus
        self._ledger_handler = FailAndRefundHandler(
            uow=self._uow,
            account_repo=SqliteAccountRepository(self._uow),
            txn_repo=SqliteTransactionRepository(self._uow),
            event_bus=self._event_bus
        )

    def refund_or_fail(self, transaction_id: int) -> None:
        command = FailAndRefundCommand(transaction_id=transaction_id)
        self._ledger_handler.handle(command)