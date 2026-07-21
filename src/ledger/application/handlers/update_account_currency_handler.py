import time
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.update_account_currency_command import UpdateAccountCurrencyCommand
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.common.domain.exceptions import AccountNotFoundError, ConcurrencyException

class UpdateAccountCurrencyHandler:
    MAX_RETRIES = 3
    BASE_DELAY = 0.1

    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository):
        self._uow = uow
        self._repo = account_repo

    def handle(self, cmd: UpdateAccountCurrencyCommand) -> None:
        attempt = 0
        while True:
            try:
                with self._uow:
                    account = self._repo.get_by_id(cmd.account_id)
                    if not account: 
                        raise AccountNotFoundError("Account not found.")
                    
                    new_currency_code = CurrencyCode(cmd.currency_code)
                    account.change_currency(new_currency_code)
                    
                    self._repo.update(account)
                    return 
                    
            except ConcurrencyException:
                attempt += 1
                if attempt >= self.MAX_RETRIES:
                    raise
                
                time.sleep(self.BASE_DELAY * (2 ** (attempt - 1)))