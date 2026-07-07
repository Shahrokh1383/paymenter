from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

# Identity Infrastructure Adapters
from src.identity.infrastructure.persistence.sqlite_user_repository import SqliteUserRepository
from src.identity.infrastructure.persistence.sqlite_merchant_repository import SqliteMerchantRepository

# Identity Application Handlers
from src.identity.application.handlers.identity_handlers import OnboardMerchantHandler, ToggleMerchantHandler
from src.identity.application.handlers.identity_query_handlers import GetAllUsersHandler, SearchUsersHandler, GetAllMerchantsHandler
from src.identity.application.handlers.register_user_handler import RegisterUserHandler
from src.identity.application.handlers.on_account_created_handler import OnAccountCreatedHandler
from src.identity.application.handlers.read_model_handlers import (
    UserRegisteredReadModelHandler, AccountCreatedReadModelHandler, CardAssignedReadModelHandler
)
from src.identity.application.handlers.merchant_read_model_handlers import (
    MerchantOnboardedReadModelHandler, MerchantToggledReadModelHandler
)

# Identity Domain Events
from src.identity.domain.events.user_events import UserRegisteredEvent
from src.ledger.domain.events.account_events import AccountCreatedEvent
from src.identity.domain.events.card_events import CardAssignedEvent
from src.identity.domain.events.merchant_events import (
    MerchantOnboardedEvent, MerchantActivatedEvent, MerchantDeactivatedEvent
)

def register_identity(container):
    bus = container.event_bus

    # --- Event Subscribers ---
    bus.subscribe(UserRegisteredEvent, lambda event: UserRegisteredReadModelHandler(SqliteUnitOfWork()).handle(event))
    bus.subscribe(AccountCreatedEvent, lambda event: AccountCreatedReadModelHandler(SqliteUnitOfWork()).handle(event))
    bus.subscribe(CardAssignedEvent, lambda event: CardAssignedReadModelHandler(SqliteUnitOfWork()).handle(event))
    bus.subscribe(AccountCreatedEvent, lambda event: OnAccountCreatedHandler(SqliteUnitOfWork(), bus).handle(event))
    bus.subscribe(MerchantOnboardedEvent, lambda event: MerchantOnboardedReadModelHandler(SqliteUnitOfWork()).handle(event))
    
    toggled_handler = MerchantToggledReadModelHandler(SqliteUnitOfWork())
    bus.subscribe(MerchantActivatedEvent, lambda event: toggled_handler.handle_activated(event))
    bus.subscribe(MerchantDeactivatedEvent, lambda event: toggled_handler.handle_deactivated(event))

    # --- Handler Factories (Enforces Strict DIP in Delivery Layer) ---
    def get_all_users_handler(uow: SqliteUnitOfWork) -> GetAllUsersHandler:
        return GetAllUsersHandler(SqliteUserRepository(uow))

    def get_search_users_handler(uow: SqliteUnitOfWork) -> SearchUsersHandler:
        return SearchUsersHandler(SqliteUserRepository(uow))

    def get_all_merchants_handler(uow: SqliteUnitOfWork) -> GetAllMerchantsHandler:
        return GetAllMerchantsHandler(SqliteMerchantRepository(uow))

    def get_onboard_merchant_handler(uow: SqliteUnitOfWork) -> OnboardMerchantHandler:
        return OnboardMerchantHandler(uow, SqliteMerchantRepository(uow), bus)

    def get_toggle_merchant_handler(uow: SqliteUnitOfWork) -> ToggleMerchantHandler:
        return ToggleMerchantHandler(uow, SqliteMerchantRepository(uow), bus)

    def get_register_user_handler(uow: SqliteUnitOfWork) -> RegisterUserHandler:
        return RegisterUserHandler(uow, SqliteUserRepository(uow), bus)

    # Bind factories to container
    container.get_all_users_handler = get_all_users_handler
    container.get_search_users_handler = get_search_users_handler
    container.get_all_merchants_handler = get_all_merchants_handler
    container.get_onboard_merchant_handler = get_onboard_merchant_handler
    container.get_toggle_merchant_handler = get_toggle_merchant_handler
    container.get_register_user_handler = get_register_user_handler