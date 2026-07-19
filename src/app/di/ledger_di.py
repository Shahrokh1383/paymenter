from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

# Ledger Infrastructure Adapters
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_repository import SqliteTransactionRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_read_model import SqliteTransactionReadModel
from src.ledger.infrastructure.persistence.sqlite_account_read_model import SqliteAccountReadModel
from src.ledger.infrastructure.adapters.sqlite_system_account_resolver import SqliteSystemAccountResolver
from src.ledger.infrastructure.persistence.sqlite_currency_repository import SqliteCurrencyRepository
from src.ledger.infrastructure.persistence.sqlite_currency_query_repository import SqliteCurrencyQueryRepository
from src.ledger.infrastructure.persistence.sqlite_escrow_account_read_model import SqliteEscrowAccountReadModel

# Ledger Application Handlers
from src.ledger.application.handlers.hold_funds_handler import HoldFundsHandler
from src.ledger.application.handlers.complete_funds_handler import CompleteFundsHandler
from src.ledger.application.handlers.fail_and_refund_handler import FailAndRefundHandler
from src.ledger.application.handlers.get_transactions_handler import GetTransactionsHandler
from src.ledger.application.handlers.topup_account_handler import TopupAccountHandler
from src.ledger.application.handlers.update_account_currency_handler import UpdateAccountCurrencyHandler
from src.ledger.application.handlers.get_all_accounts_handler import GetAllAccountsHandler
from src.ledger.application.handlers.create_currency_handler import CreateCurrencyHandler, EscrowBootstrapperEventHandler
from src.ledger.application.handlers.toggle_currency_handler import ToggleCurrencyHandler
from src.ledger.application.handlers.get_all_currencies_handler import GetAllCurrenciesHandler
from src.ledger.application.handlers.get_active_currencies_handler import GetActiveCurrenciesHandler
from src.ledger.application.handlers.get_all_escrow_accounts_handler import GetAllEscrowAccountsHandler
from src.ledger.application.handlers.create_account_handler import CreateAccountHandler

# Events
from src.ledger.domain.events.currency_events import CurrencyCreatedEvent

def register_ledger(container):

    def get_create_account_handler(uow: SqliteUnitOfWork) -> CreateAccountHandler:
        return CreateAccountHandler(uow=uow, account_repo=SqliteAccountRepository(uow), event_bus=container.event_bus)
    
    def get_hold_funds_handler(uow: SqliteUnitOfWork) -> HoldFundsHandler:
        return HoldFundsHandler(uow=uow, account_repo=SqliteAccountRepository(uow), txn_repo=SqliteTransactionRepository(uow), system_account_resolver=SqliteSystemAccountResolver(uow))

    def get_complete_funds_handler(uow: SqliteUnitOfWork) -> CompleteFundsHandler:
        return CompleteFundsHandler(uow=uow, account_repo=SqliteAccountRepository(uow), txn_repo=SqliteTransactionRepository(uow), event_bus=container.event_bus, system_account_resolver=SqliteSystemAccountResolver(uow))

    def get_fail_and_refund_handler(uow: SqliteUnitOfWork) -> FailAndRefundHandler:
        return FailAndRefundHandler(uow=uow, account_repo=SqliteAccountRepository(uow), txn_repo=SqliteTransactionRepository(uow), event_bus=container.event_bus, system_account_resolver=SqliteSystemAccountResolver(uow))

    def get_transactions_handler(uow: SqliteUnitOfWork) -> GetTransactionsHandler:
        return GetTransactionsHandler(query_port=SqliteTransactionReadModel(uow))

    def get_topup_account_handler(uow: SqliteUnitOfWork) -> TopupAccountHandler:
        return TopupAccountHandler(uow=uow, account_repo=SqliteAccountRepository(uow))

    def get_update_account_currency_handler(uow: SqliteUnitOfWork) -> UpdateAccountCurrencyHandler:
        return UpdateAccountCurrencyHandler(uow=uow, account_repo=SqliteAccountRepository(uow))

    def get_all_accounts_handler(uow: SqliteUnitOfWork) -> GetAllAccountsHandler:
        return GetAllAccountsHandler(query_port=SqliteAccountReadModel(uow))

    def get_create_currency_handler(uow: SqliteUnitOfWork) -> CreateCurrencyHandler:
        # Bug #1 Fix: Removed account_repo injection. Handler is now pure.
        return CreateCurrencyHandler(uow=uow, currency_repo=SqliteCurrencyRepository(uow), event_bus=container.event_bus)
    
    def get_escrow_bootstrapper_event_handler(uow: SqliteUnitOfWork) -> EscrowBootstrapperEventHandler:
        return EscrowBootstrapperEventHandler(uow=uow, account_repo=SqliteAccountRepository(uow))
        
    def get_toggle_currency_handler(uow: SqliteUnitOfWork) -> ToggleCurrencyHandler:
        return ToggleCurrencyHandler(uow=uow, currency_repo=SqliteCurrencyRepository(uow), event_bus=container.event_bus)

    def get_all_currencies_handler(uow: SqliteUnitOfWork) -> GetAllCurrenciesHandler:
        return GetAllCurrenciesHandler(query_port=SqliteCurrencyQueryRepository(uow))

    def get_active_currencies_handler(uow: SqliteUnitOfWork) -> GetActiveCurrenciesHandler:
        return GetActiveCurrenciesHandler(query_port=SqliteCurrencyQueryRepository(uow))
    
    def get_all_escrow_accounts_handler(uow: SqliteUnitOfWork) -> GetAllEscrowAccountsHandler:
        return GetAllEscrowAccountsHandler(query_port=SqliteEscrowAccountReadModel(uow))

    # Bind factories to container
    container.get_create_account_handler = get_create_account_handler
    container.get_hold_funds_handler = get_hold_funds_handler
    container.get_complete_funds_handler = get_complete_funds_handler
    container.get_fail_and_refund_handler = get_fail_and_refund_handler
    container.get_transactions_handler = get_transactions_handler
    container.get_topup_account_handler = get_topup_account_handler
    container.get_update_account_currency_handler = get_update_account_currency_handler
    container.get_all_accounts_handler = get_all_accounts_handler
    container.get_create_currency_handler = get_create_currency_handler
    container.get_toggle_currency_handler = get_toggle_currency_handler
    container.get_all_currencies_handler = get_all_currencies_handler
    container.get_active_currencies_handler = get_active_currencies_handler
    container.get_all_escrow_accounts_handler = get_all_escrow_accounts_handler
    bootstrapper_handler = get_escrow_bootstrapper_event_handler(SqliteUnitOfWork())
    container.event_bus.subscribe(CurrencyCreatedEvent, bootstrapper_handler.handle)