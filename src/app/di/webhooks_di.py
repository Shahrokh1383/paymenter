from src.webhook.application.handlers.webhook_outbox_event_handler import WebhookOutboxEventHandler
from src.webhook.application.handlers.get_all_deliveries_handler import GetAllDeliveriesHandler
from src.webhook.application.handlers.retry_webhook_delivery_handler import RetryWebhookDeliveryHandler
from src.webhook.infrastructure.persistence.sqlite_webhook_outbox_repository import SqliteWebhookOutboxRepository
from src.webhook.infrastructure.persistence.sqlite_webhook_delivery_repository import SqliteWebhookDeliveryRepository
from src.webhook.infrastructure.persistence.sqlite_merchant_webhook_config_adapter import SqliteMerchantWebhookConfigAdapter
from src.common.infrastructure.database import create_connection
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)

def register_webhooks(container):
    merchant_webhook_config_adapter = SqliteMerchantWebhookConfigAdapter(connection_factory=create_connection)

    def get_webhook_outbox_handler():
        uow = SqliteUnitOfWork()
        return WebhookOutboxEventHandler(
            uow=uow,
            outbox_repo=SqliteWebhookOutboxRepository(uow),
            merchant_config_port=merchant_webhook_config_adapter
        )

    def get_all_deliveries_handler(uow: SqliteUnitOfWork) -> GetAllDeliveriesHandler:
        return GetAllDeliveriesHandler(SqliteWebhookDeliveryRepository(uow))

    def get_retry_delivery_handler(uow: SqliteUnitOfWork) -> RetryWebhookDeliveryHandler:
        return RetryWebhookDeliveryHandler(uow, SqliteWebhookDeliveryRepository(uow))

    container.event_bus.subscribe(TransactionCompletedEvent, lambda e: get_webhook_outbox_handler().handle_completed(e))
    container.event_bus.subscribe(TransactionFailedEvent, lambda e: get_webhook_outbox_handler().handle_failed(e))
    container.event_bus.subscribe(TransactionRefundedEvent, lambda e: get_webhook_outbox_handler().handle_refunded(e))
    container.get_all_deliveries_handler = get_all_deliveries_handler
    container.get_retry_delivery_handler = get_retry_delivery_handler