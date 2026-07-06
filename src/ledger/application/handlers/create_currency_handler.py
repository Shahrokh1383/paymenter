from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.commands.create_currency_command import CreateCurrencyCommand
from src.ledger.application.ports.currency_command_port import CurrencyCommandPort
from src.ledger.domain.repositories import AccountRepository
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money

class CreateCurrencyHandler:
    """
    Handles creation of a new currency.
    Automatically bootstraps the required System Escrow account for double-entry ledger balancing.
    """
    def __init__(self, uow: UnitOfWork, currency_repo: CurrencyCommandPort, account_repo: AccountRepository):
        self._uow = uow
        self._currency_repo = currency_repo
        self._account_repo = account_repo

    def handle(self, command: CreateCurrencyCommand) -> int:
        with self._uow:
            # 1. Create the currency
            currency_id = self._currency_repo.add_currency(command.name, command.code)
            
            # 2. Automatically bootstrap the System Escrow Account for this currency
            system_account_number = str(9000000000 + currency_id)
            
            escrow_account = Account(
                id=0,
                user_id=None,
                merchant_id=None,
                account_number=AccountNumber(system_account_number),
                balance=Money('0.00', command.code)
            )
            self._account_repo.add(escrow_account)
            
            self._uow.commit()
            return currency_id