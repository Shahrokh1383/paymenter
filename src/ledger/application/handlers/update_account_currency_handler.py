from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.update_account_currency_command import UpdateAccountCurrencyCommand
from src.ledger.application.ports.currency_query_port import CurrencyQueryPort

class UpdateAccountCurrencyHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, currency_query: CurrencyQueryPort):
        self._uow = uow
        self._repo = account_repo
        self._currency_query = currency_query

    def handle(self, cmd: UpdateAccountCurrencyCommand) -> None:
        with self._uow:
            account = self._repo.get_by_id(cmd.account_id)
            if not account: 
                raise ValueError("Account not found.")
            
            currency_code = self._currency_query.get_currency_code_by_id(cmd.currency_id)
            
            # Aggregate protects its own invariant and updates in-memory state (Fixes EC-6)
            account.change_currency(currency_code)
            
            # Persist the fully updated aggregate state
            self._repo.update(account)
            self._uow.commit()