from src.notifications.application.handlers.receipt_email_handler import ReceiptEmailHandler
from src.notifications.application.handlers.otp_notification_handler import OtpNotificationHandler
from src.notifications.infrastructure.smtp.smtp_adapter import SmtpAdapter
from src.notifications.infrastructure.persistence.sqlite_merchant_details_adapter import SqliteMerchantDetailsAdapter
from src.notifications.infrastructure.persistence.sqlite_idempotency_adapter import SqliteIdempotencyAdapter
from src.notifications.infrastructure.persistence.sqlite_account_owner_adapter import SqliteAccountOwnerAdapter
from src.common.infrastructure.database import create_connection

from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)
from src.checkout.domain.events.otp_requested_event import OtpRequestedEvent
from src.notifications.application.handlers.webhook_outbox_event_handler import WebhookOutboxEventHandler
from src.notifications.infrastructure.persistence.sqlite_webhook_outbox_repository import SqliteWebhookOutboxRepository
from src.notifications.infrastructure.persistence.sqlite_merchant_webhook_config_adapter import SqliteMerchantWebhookConfigAdapter
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork


def register_notifications(container):
    """
    Registers cross-context event subscriptions for the Notifications bounded context.
    """
    smtp_adapter = SmtpAdapter()
    merchant_adapter = SqliteMerchantDetailsAdapter()
    idempotency_adapter = SqliteIdempotencyAdapter(connection_factory=create_connection)
    account_resolver = SqliteAccountOwnerAdapter()
    
    receipt_handler = ReceiptEmailHandler(
        dispatcher=smtp_adapter,
        merchant_port=merchant_adapter,
        idempotency_port=idempotency_adapter,
        account_resolver=account_resolver
    )
    
    otp_handler = OtpNotificationHandler(
        dispatcher=smtp_adapter,
        idempotency_port=idempotency_adapter
    )
    
    merchant_webhook_config_adapter = SqliteMerchantWebhookConfigAdapter(connection_factory=create_connection)

    def get_webhook_outbox_handler():
        uow = SqliteUnitOfWork()
        return WebhookOutboxEventHandler(
            uow=uow,
            outbox_repo=SqliteWebhookOutboxRepository(uow),
            merchant_config_port=merchant_webhook_config_adapter
        )
    
    container.event_bus.subscribe(TransactionCompletedEvent, lambda e: get_webhook_outbox_handler().handle_completed(e))
    container.event_bus.subscribe(TransactionFailedEvent, lambda e: get_webhook_outbox_handler().handle_failed(e))
    container.event_bus.subscribe(TransactionRefundedEvent, lambda e: get_webhook_outbox_handler().handle_refunded(e))
    container.event_bus.subscribe(OtpRequestedEvent, otp_handler.handle_otp_requested)