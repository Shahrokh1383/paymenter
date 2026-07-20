from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.exceptions import AccountNotFoundError, CurrencyMismatchError
from src.ledger.domain.repositories import AccountRepository, TransactionRepository
from src.ledger.domain.ports.system_account_resolver_port import SystemAccountResolverPort
from src.ledger.domain.services.double_entry_ledger import DoubleEntryLedger
from src.common.domain.value_objects.money import Money 
from src.ledger.application.commands.hold_funds_command import HoldFundsCommand

class HoldFundsHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, txn_repo: TransactionRepository, system_account_resolver: SystemAccountResolverPort):
        self._uow = uow
        self._account_repo = account_repo
        self._txn_repo = txn_repo
        self._system_account_resolver = system_account_resolver

    def handle(self, command: HoldFundsCommand) -> str:
        with self._uow:
            from_acc = self._account_repo.get_by_id(command.from_account_id)
            to_acc = self._account_repo.get_by_id(command.to_account_id)
            
            if not from_acc or not to_acc:
                raise AccountNotFoundError("Source or Destination account does not exist.")
                
            if from_acc.balance.currency != to_acc.balance.currency:
                raise CurrencyMismatchError("Source and Destination accounts must have the same currency.")

            amount_vo = Money(command.amount, from_acc.balance.currency)
            
            escrow_acc = self._system_account_resolver.get_escrow_account(from_acc.balance.currency)

            if from_acc.id == escrow_acc.id:
                from_acc = escrow_acc
            if to_acc.id == escrow_acc.id:
                to_acc = escrow_acc

            txn = DoubleEntryLedger.hold_funds(
                from_acc=from_acc, 
                to_acc=to_acc, 
                amount=amount_vo, 
                escrow_acc=escrow_acc,
                merchant_id=command.merchant_id, 
                user_email=command.user_email
            )
            
            self._account_repo.update(from_acc)
            if to_acc is not from_acc:
                self._account_repo.update(to_acc)
            if escrow_acc is not from_acc and escrow_acc is not to_acc:
                self._account_repo.update(escrow_acc)
                
            self._txn_repo.add(txn)
            self._uow.commit()
            
            return txn.id