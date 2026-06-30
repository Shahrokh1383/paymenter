from src.notifications.application.handlers.receipt_email_handler import ReceiptEmailHandler
from src.notifications.application.handlers.otp_notification_handler import OtpNotificationHandler
from src.notifications.infrastructure.smtp.smtp_adapter import SmtpAdapter
from src.notifications.infrastructure.persistence.sqlite_merchant_details_adapter import SqliteMerchantDetailsAdapter
from src.notifications.infrastructure.persistence.sqlite_idempotency_adapter import SqliteIdempotencyAdapter

# Events (Cross-Context Subscriptions)
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)
from src.checkout.domain.events.payment_initiated_event import PaymentInitiatedEvent
from src.checkout.domain.events.otp_requested_event import OtpRequestedEvent


def register_notifications(container):
    """
    Registers cross-context event subscriptions for the Notifications bounded context.
    """
    smtp_adapter = SmtpAdapter()
    merchant_adapter = SqliteMerchantDetailsAdapter()
    idempotency_adapter = SqliteIdempotencyAdapter()
    
    receipt_handler = ReceiptEmailHandler(
        dispatcher=smtp_adapter,
        merchant_port=merchant_adapter,
        idempotency_port=idempotency_adapter
    )
    
    otp_handler = OtpNotificationHandler(
        dispatcher=smtp_adapter,
        idempotency_port=idempotency_adapter
    )
    
    container.event_bus.subscribe(TransactionCompletedEvent, receipt_handler.handle_completed)
    container.event_bus.subscribe(TransactionFailedEvent, receipt_handler.handle_failed)
    container.event_bus.subscribe(TransactionRefundedEvent, receipt_handler.handle_refunded)
    container.event_bus.subscribe(PaymentInitiatedEvent, receipt_handler.handle_initiated)
    container.event_bus.subscribe(OtpRequestedEvent, otp_handler.handle_otp_requested)