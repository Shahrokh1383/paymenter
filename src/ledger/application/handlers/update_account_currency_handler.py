from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.update_account_currency_command import UpdateAccountCurrencyCommand

class UpdateAccountCurrencyHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository):
        self._uow = uow
        self._repo = account_repo

    def handle(self, cmd: UpdateAccountCurrencyCommand) -> None:
        with self._uow:
            account = self._repo.get_by_id(cmd.account_id)
            if not account: 
                raise ValueError("Account not found.")
            
            # Aggregate protects its own invariant and updates in-memory state
            account.change_currency(cmd.currency_code)
            
            # Persist the fully updated aggregate state
            self._repo.update(account)
            self._uow.commit()