import hashlib
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
    Strictly publishes an event. Does not instantiate other aggregates.
    """
    def __init__(self, uow: UnitOfWork, currency_repo: CurrencyRepository, event_bus: EventBus):
        self._uow = uow
        self._currency_repo = currency_repo
        self._event_bus = event_bus

    def handle(self, command: CreateCurrencyCommand) -> int:
        with self._uow:
            code = CurrencyCode(command.code)
            
            if self._currency_repo.get_by_code(code) is not None:
                raise CurrencyAlreadyExistsError(f"Currency with code {command.code} already exists.")

            currency = Currency.create(id=0, name=command.name, code=code)
            currency_id = self._currency_repo.add(currency)
            currency.id = currency_id
            
            self._uow.commit()
            
            self._event_bus.publish(
                CurrencyCreatedEvent(currency_id=currency_id, name=command.name, code=code)
            )
            
            return currency_id


class EscrowBootstrapperEventHandler:
    """
    Listens to CurrencyCreatedEvent to provision the System Escrow account.
    Uses a deterministic, DB-independent algorithm for AccountNumber generation (Bug #1 Fix).
    Implements Idempotency to prevent duplicate accounts on retry (Bug #3 Fix).
    """
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository):
        self._uow = uow
        self._account_repo = account_repo

    def _generate_deterministic_account_number(self, currency_code: str) -> str:
        """Generates a 10-digit account number using SHA-256, independent of DB sequences."""
        hash_obj = hashlib.sha256(currency_code.encode('utf-8'))
        hash_int = int(hash_obj.hexdigest(), 16)
        # Modulo 10 billion ensures max 10 digits, zfill ensures exactly 10 digits
        return str(hash_int % 10000000000).zfill(10)

    def handle(self, event: CurrencyCreatedEvent) -> None:
        with self._uow:
            system_account_number_str = self._generate_deterministic_account_number(event.code.value)
            
            existing_account = self._account_repo.get_by_account_number(system_account_number_str)
            if existing_account:
                return
            
            escrow_account = Account(
                id=0,
                user_id=None,
                merchant_id=None,
                account_number=AccountNumber(system_account_number_str),
                balance=Money('0.00', event.code),
                pending_holds=Money('0.00', event.code),
                open_authorizations=0
            )
            self._account_repo.add(escrow_account)
            self._uow.commit()