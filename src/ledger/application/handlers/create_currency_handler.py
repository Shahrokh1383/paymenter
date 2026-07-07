from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.application.commands.create_currency_command import CreateCurrencyCommand
from src.ledger.domain.repositories import CurrencyRepository, AccountRepository
from src.ledger.domain.entities.currency import Currency
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money
from src.ledger.domain.events.currency_events import CurrencyCreatedEvent
from src.common.domain.exceptions import CurrencyAlreadyExistsError

class CreateCurrencyHandler:
    """
    Handles creation of a new currency.
    Automatically bootstraps the required System Escrow account for double-entry ledger balancing.
    """
    def __init__(
        self, 
        uow: UnitOfWork, 
        currency_repo: CurrencyRepository, 
        account_repo: AccountRepository,
        event_bus: EventBus
    ):
        self._uow = uow
        self._currency_repo = currency_repo
        self._account_repo = account_repo
        self._event_bus = event_bus

    def handle(self, command: CreateCurrencyCommand) -> int:
        with self._uow:
            code = CurrencyCode(command.code)
            
            if self._currency_repo.get_by_code(code) is not None:
                raise CurrencyAlreadyExistsError(f"Currency with code {command.code} already exists.")

            # 1. Create the currency aggregate
            currency = Currency.create(id=0, name=command.name, code=code)
            currency_id = self._currency_repo.add(currency)
            currency.id = currency_id
            
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
            
            self._event_bus.publish(
                CurrencyCreatedEvent(currency_id=currency_id, name=command.name, code=code)
            )
            
            return currency_id