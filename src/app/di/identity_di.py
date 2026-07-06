from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

from src.identity.application.handlers.on_account_created_handler import OnAccountCreatedHandler
from src.identity.application.handlers.read_model_handlers import (
    UserRegisteredReadModelHandler,
    AccountCreatedReadModelHandler,
    CardAssignedReadModelHandler
)
from src.identity.application.handlers.merchant_read_model_handlers import (
    MerchantOnboardedReadModelHandler,
    MerchantToggledReadModelHandler
)

from src.identity.domain.events.user_events import UserRegisteredEvent
from src.ledger.domain.events.account_events import AccountCreatedEvent
from src.identity.domain.events.card_events import CardAssignedEvent
from src.identity.domain.events.merchant_events import (
    MerchantOnboardedEvent,
    MerchantActivatedEvent,
    MerchantDeactivatedEvent
)

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

    bus.subscribe(AccountCreatedEvent, lambda event: OnAccountCreatedHandler(
        SqliteUnitOfWork(),
        bus
    ).handle(event))

    bus.subscribe(MerchantOnboardedEvent, lambda event: MerchantOnboardedReadModelHandler(
        SqliteUnitOfWork()
    ).handle(event))

    toggled_handler = MerchantToggledReadModelHandler(SqliteUnitOfWork())
    bus.subscribe(MerchantActivatedEvent, lambda event: toggled_handler.handle_activated(event))
    bus.subscribe(MerchantDeactivatedEvent, lambda event: toggled_handler.handle_deactivated(event))