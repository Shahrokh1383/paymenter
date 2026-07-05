from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

# Identity Handlers (domain event subscribers)
from src.identity.application.handlers.on_account_created_handler import OnAccountCreatedHandler
from src.identity.application.handlers.read_model_handlers import (
    UserRegisteredReadModelHandler,
    AccountCreatedReadModelHandler,
    CardAssignedReadModelHandler
)
from src.identity.application.handlers.on_account_balance_updated_handler import OnAccountBalanceUpdatedHandler

# Events
from src.identity.domain.events.user_events import UserRegisteredEvent
from src.ledger.domain.events.account_events import AccountCreatedEvent
from src.identity.domain.events.card_events import CardAssignedEvent
from src.ledger.domain.events.account_balance_updated_event import AccountBalanceUpdatedEvent

def register_identity(container):
    bus = container.event_bus

    def uow_factory():
        return SqliteUnitOfWork()

    bus.subscribe(UserRegisteredEvent, lambda event: UserRegisteredReadModelHandler(
        SqliteUnitOfWork()
    ).handle(event))

    bus.subscribe(AccountCreatedEvent, lambda event: AccountCreatedReadModelHandler(
        SqliteUnitOfWork()
    ).handle(event))

    bus.subscribe(CardAssignedEvent, lambda event: CardAssignedReadModelHandler(
        SqliteUnitOfWork()
    ).handle(event))

    # Identity card assignment handler:
    bus.subscribe(AccountCreatedEvent, lambda event: OnAccountCreatedHandler(
        SqliteUnitOfWork(),
        bus
    ).handle(event))

    bus.subscribe(AccountBalanceUpdatedEvent, lambda event: OnAccountBalanceUpdatedHandler(
        SqliteUnitOfWork()
    ).handle(event))