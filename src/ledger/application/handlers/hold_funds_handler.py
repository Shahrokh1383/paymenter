from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.exceptions import AccountNotFoundError, CurrencyMismatchError
from src.ledger.domain.repositories import AccountRepository, TransactionRepository
from src.ledger.domain.services.double_entry_ledger import DoubleEntryLedger
from src.common.domain.value_objects.money import Money 
from src.ledger.application.commands.hold_funds_command import HoldFundsCommand
from src.ledger.application.ledger_config import SYSTEM_ESCROW_ACCOUNT_ID

class HoldFundsHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, txn_repo: TransactionRepository):
        self._uow = uow
        self._account_repo = account_repo
        self._txn_repo = txn_repo

    def handle(self, command: HoldFundsCommand) -> int:
        with self._uow:
            from_acc = self._account_repo.get_by_id(command.from_account_id)
            to_acc = self._account_repo.get_by_id(command.to_account_id)
            escrow_acc = self._account_repo.get_by_id(SYSTEM_ESCROW_ACCOUNT_ID)
            
            if not from_acc or not to_acc or not escrow_acc:
                raise AccountNotFoundError("Source, Destination, or System Escrow account does not exist.")
                
            if from_acc.balance.currency != to_acc.balance.currency:
                raise CurrencyMismatchError("Source and Destination accounts must have the same currency.")

            # Translate primitive Decimal to Domain Value Object using auto-detected currency
            amount_vo = Money(command.amount, from_acc.balance.currency)

            txn = DoubleEntryLedger.hold_funds(
                from_acc=from_acc, 
                to_acc=to_acc, 
                amount=amount_vo, 
                escrow_acc=escrow_acc,
                merchant_id=command.merchant_id, 
                user_email=command.user_email
            )
            
            self._account_repo.update(from_acc)
            self._account_repo.update(escrow_acc)
            txn_id = self._txn_repo.add(txn)
            self._uow.commit()
            
            return txn_id