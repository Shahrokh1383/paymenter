from src.common.infrastructure.event_bus import InMemoryEventBus

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

class DIContainer:
    """
    Centralized Dependency Injection Container.
    Manages global singletons and cross-context Event Bus subscriptions.
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