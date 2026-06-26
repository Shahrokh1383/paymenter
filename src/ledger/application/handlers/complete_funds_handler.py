from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.exceptions import AccountNotFoundError, InvalidTransactionStateError
from src.ledger.domain.repositories import AccountRepository, TransactionRepository
from src.ledger.domain.services.double_entry_ledger import DoubleEntryLedger
from src.ledger.application.commands.complete_funds_command import CompleteFundsCommand

class CompleteFundsHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, txn_repo: TransactionRepository):
        self._uow = uow
        self._account_repo = account_repo
        self._txn_repo = txn_repo

    def handle(self, command: CompleteFundsCommand) -> None:
        with self._uow:
            txn = self._txn_repo.get_by_id(command.transaction_id)
            if not txn:
                raise InvalidTransactionStateError("Transaction not found.")
                
            to_acc = self._account_repo.get_by_id(txn.to_account_id)
            if not to_acc:
                raise AccountNotFoundError("Destination account not found.")

            DoubleEntryLedger.complete_funds(txn, to_acc)
            
            self._txn_repo.update(txn)
            self._account_repo.update(to_acc)
            self._uow.commit()