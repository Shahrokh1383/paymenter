from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.update_account_currency_command import UpdateAccountCurrencyCommand

class UpdateAccountCurrencyHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository):
        self._uow, self._repo = uow, account_repo

    def handle(self, cmd: UpdateAccountCurrencyCommand) -> None:
        with self._uow:
            account = self._repo.get_by_id(cmd.account_id)
            if not account: raise ValueError("Account not found.")
            if not account.can_change_currency():
                raise ValueError("Cannot change currency on an account with a balance > 0.")
            self._repo.update_currency(cmd.account_id, cmd.currency_id)
            self._uow.commit()