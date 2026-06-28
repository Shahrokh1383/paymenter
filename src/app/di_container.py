from src.common.infrastructure.event_bus import InMemoryEventBus
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

# Ledger Events
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)
# Checkout Events
from src.checkout.domain.events.payment_initiated_event import PaymentInitiatedEvent

# Notifications Handler & Adapters
from src.notifications.application.handlers.receipt_email_handler import ReceiptEmailHandler
from src.notifications.infrastructure.smtp.smtp_adapter import SmtpAdapter
from src.notifications.infrastructure.persistence.sqlite_merchant_details_adapter import SqliteMerchantDetailsAdapter

# Ledger Infrastructure Adapters
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_repository import SqliteTransactionRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_read_model import SqliteTransactionReadModel
from src.ledger.infrastructure.persistence.sqlite_account_read_model import SqliteAccountReadModel
from src.ledger.infrastructure.persistence.sqlite_currency_resolver import SqliteCurrencyResolver

# Ledger Application Handlers
from src.ledger.application.handlers.hold_funds_handler import HoldFundsHandler
from src.ledger.application.handlers.complete_funds_handler import CompleteFundsHandler
from src.ledger.application.handlers.fail_and_refund_handler import FailAndRefundHandler
from src.ledger.application.handlers.get_transactions_handler import GetTransactionsHandler
from src.ledger.application.handlers.topup_account_handler import TopupAccountHandler
from src.ledger.application.handlers.update_account_currency_handler import UpdateAccountCurrencyHandler
from src.ledger.application.handlers.get_all_accounts_handler import GetAllAccountsHandler


class DIContainer:
    """
    Centralized Dependency Injection Container.
    Manages global singletons, cross-context Event Bus subscriptions, 
    and provides factory methods for request-scoped handlers (TD-9).
    """
    def __init__(self):
        self.event_bus = InMemoryEventBus()
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        # 1. Instantiate Infrastructure Adapters
        smtp_adapter = SmtpAdapter()
        merchant_adapter = SqliteMerchantDetailsAdapter()
        
        # 2. Instantiate Cross-Context Handlers
        receipt_handler = ReceiptEmailHandler(
            dispatcher=smtp_adapter,
            merchant_port=merchant_adapter
        )
        
        # 3. Subscribe to Ledger Events
        self.event_bus.subscribe(TransactionCompletedEvent, receipt_handler.handle_completed)
        self.event_bus.subscribe(TransactionFailedEvent, receipt_handler.handle_failed)
        self.event_bus.subscribe(TransactionRefundedEvent, receipt_handler.handle_refunded)
        
        # 4. Subscribe to Checkout Events
        self.event_bus.subscribe(PaymentInitiatedEvent, receipt_handler.handle_initiated)

    # These factories enforce IoC. Controllers receive fully wired handlers 
    # without knowing about concrete Repository implementations.

    def get_hold_funds_handler(self, uow: SqliteUnitOfWork) -> HoldFundsHandler:
        return HoldFundsHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            transaction_repo=SqliteTransactionRepository(uow)
        )

    def get_complete_funds_handler(self, uow: SqliteUnitOfWork) -> CompleteFundsHandler:
        return CompleteFundsHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            transaction_repo=SqliteTransactionRepository(uow),
            event_bus=self.event_bus
        )

    def get_fail_and_refund_handler(self, uow: SqliteUnitOfWork) -> FailAndRefundHandler:
        return FailAndRefundHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            transaction_repo=SqliteTransactionRepository(uow),
            event_bus=self.event_bus
        )

    def get_transactions_handler(self, uow: SqliteUnitOfWork) -> GetTransactionsHandler:
        return GetTransactionsHandler(
            query_model=SqliteTransactionReadModel(uow)
        )

    def get_topup_account_handler(self, uow: SqliteUnitOfWork) -> TopupAccountHandler:
        return TopupAccountHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow)
        )

    def get_update_account_currency_handler(self, uow: SqliteUnitOfWork) -> UpdateAccountCurrencyHandler:
        return UpdateAccountCurrencyHandler(
            uow=uow,
            account_repo=SqliteAccountRepository(uow),
            currency_query=SqliteCurrencyResolver(uow)
        )

    def get_all_accounts_handler(self, uow: SqliteUnitOfWork) -> GetAllAccountsHandler:
        return GetAllAccountsHandler(
            query_port=SqliteAccountReadModel(uow)
        )