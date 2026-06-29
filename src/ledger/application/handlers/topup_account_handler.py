from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.value_objects.money import Money
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.topup_account_command import TopupAccountCommand

class TopupAccountHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository):
        self._uow = uow
        self._account_repo = account_repo

    def handle(self, command: TopupAccountCommand) -> None:
        with self._uow:
            account = self._account_repo.get_by_id(command.account_id)
            if not account: raise ValueError("Account not found")
            topup_money = Money(command.amount, account.balance.currency)
            
            account.topup(topup_money)
            self._account_repo.update(account)
            self._uow.commit()