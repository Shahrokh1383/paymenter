from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.common.infrastructure.event_bus.outbox_event_bus_decorator import OutboxEventBusDecorator

# Ledger Infrastructure Adapters
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_repository import SqliteTransactionRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_read_model import SqliteTransactionReadModel
from src.ledger.infrastructure.persistence.sqlite_account_read_model import SqliteAccountReadModel
from src.ledger.infrastructure.adapters.sqlite_system_account_resolver import SqliteSystemAccountResolver
from src.ledger.infrastructure.persistence.sqlite_currency_command_repository import SqliteCurrencyCommandRepository

# Ledger Application Handlers
from src.ledger.application.handlers.hold_funds_handler import HoldFundsHandler
from src.ledger.application.handlers.complete_funds_handler import CompleteFundsHandler
from src.ledger.application.handlers.fail_and_refund_handler import FailAndRefundHandler
from src.ledger.application.handlers.get_transactions_handler import GetTransactionsHandler
from src.ledger.application.handlers.topup_account_handler import TopupAccountHandler
from src.ledger.application.handlers.update_account_currency_handler import UpdateAccountCurrencyHandler
from src.ledger.application.handlers.get_all_accounts_handler import GetAllAccountsHandler
from src.ledger.application.handlers.create_currency_handler import CreateCurrencyHandler


def register_ledger(container):
    """
    Registers all Ledger bounded context handler factories.
    """
    if not isinstance(container.event_bus, OutboxEventBusDecorator):
        container.event_bus = OutboxEventBusDecorator(container.event_bus)

    def get_hold_funds_handler(uow: SqliteUnitOfWork) -> HoldFundsHandler:
        return HoldFundsHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            txn_repo=SqliteTransactionRepository(uow),
            system_account_resolver=SqliteSystemAccountResolver(uow)
        )

    def get_complete_funds_handler(uow: SqliteUnitOfWork) -> CompleteFundsHandler:
        return CompleteFundsHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            txn_repo=SqliteTransactionRepository(uow),
            event_bus=container.event_bus,
            system_account_resolver=SqliteSystemAccountResolver(uow)
        )

    def get_fail_and_refund_handler(uow: SqliteUnitOfWork) -> FailAndRefundHandler:
        return FailAndRefundHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            txn_repo=SqliteTransactionRepository(uow),
            event_bus=container.event_bus,
            system_account_resolver=SqliteSystemAccountResolver(uow)
        )

    def get_transactions_handler(uow: SqliteUnitOfWork) -> GetTransactionsHandler:
        return GetTransactionsHandler(
            query_port=SqliteTransactionReadModel(uow)
        )

    def get_topup_account_handler(uow: SqliteUnitOfWork) -> TopupAccountHandler:
        return TopupAccountHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow)
        )

    def get_update_account_currency_handler(uow: SqliteUnitOfWork) -> UpdateAccountCurrencyHandler:
        return UpdateAccountCurrencyHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow)
        )

    def get_all_accounts_handler(uow: SqliteUnitOfWork) -> GetAllAccountsHandler:
        return GetAllAccountsHandler(
            query_port=SqliteAccountReadModel(uow)
        )

    def get_create_currency_handler(uow: SqliteUnitOfWork) -> CreateCurrencyHandler:
        return CreateCurrencyHandler(
            uow=uow,
            currency_repo=SqliteCurrencyCommandRepository(uow),
            account_repo=SqliteAccountRepository(uow)
        )

    # Bind factories to the main container instance
    container.get_hold_funds_handler = get_hold_funds_handler
    container.get_complete_funds_handler = get_complete_funds_handler
    container.get_fail_and_refund_handler = get_fail_and_refund_handler
    container.get_transactions_handler = get_transactions_handler
    container.get_topup_account_handler = get_topup_account_handler
    container.get_update_account_currency_handler = get_update_account_currency_handler
    container.get_all_accounts_handler = get_all_accounts_handler
    container.get_create_currency_handler = get_create_currency_handler