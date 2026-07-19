from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.common.infrastructure.generators import generate_account_number
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.create_account_command import CreateAccountCommand
from src.ledger.domain.events.account_events import AccountCreatedEvent
from src.common.domain.ports.event_bus import EventBus

class CreateAccountHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, event_bus: EventBus):
        self._uow = uow
        self._account_repo = account_repo
        self._event_bus = event_bus

    def handle(self, cmd: CreateAccountCommand) -> int:
        with self._uow:
            acc_num_str = generate_account_number(
                lambda num: self._account_repo.get_by_account_number(num) is not None
                if hasattr(self._account_repo, 'get_by_account_number') else False
            )
            account_number = AccountNumber(acc_num_str)
            currency_code = CurrencyCode(cmd.currency_code)

            # Fix: Added pending_holds and open_authorizations to satisfy Aggregate invariants.
            # Changed id=None to id=0 for codebase consistency.
            account = Account(
                id=0,
                user_id=cmd.user_id,
                merchant_id=cmd.merchant_id,
                account_number=account_number,
                balance=Money('0.00', currency_code),
                pending_holds=Money('0.00', currency_code),
                open_authorizations=0,
                version=0
            )

            account_id = self._account_repo.add(account)
            self._uow.commit()

            self._event_bus.publish(AccountCreatedEvent(
                account_id=account_id,
                user_id=cmd.user_id,
                merchant_id=cmd.merchant_id,
                account_number=account_number,
                currency_code=currency_code
            ))

            return account_id