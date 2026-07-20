import json
import hmac
import hashlib
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.notifications.domain.ports.webhook_outbox_port import WebhookOutboxPort
from src.notifications.domain.ports.merchant_webhook_config_port import MerchantWebhookConfigPort
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)

class WebhookOutboxEventHandler:
    def __init__(self, uow: UnitOfWork, outbox_repo: WebhookOutboxPort, merchant_config_port: MerchantWebhookConfigPort):
        self._uow = uow
        self._outbox_repo = outbox_repo
        self._merchant_config_port = merchant_config_port

    def handle_completed(self, event: TransactionCompletedEvent) -> None:
        self._process_event("payment.completed", event)

    def handle_failed(self, event: TransactionFailedEvent) -> None:
        self._process_event("payment.failed", event)

    def handle_refunded(self, event: TransactionRefundedEvent) -> None:
        self._process_event("payment.refunded", event)

    def _process_event(self, event_type: str, event) -> None:
        if not event.merchant_id:
            return

        # Instantiates UoW. Thanks to ContextVars, if called inside a parent UoW, 
        # it joins the exact same transaction.
        with self._uow:
            config = self._merchant_config_port.get_config(event.merchant_id)
            if not config or not config.webhook_enabled or not config.webhook_url or not config.webhook_secret:
                return

            payload = {
                "event": event_type,
                "transaction_id": event.transaction_id,
                "merchant_id": event.merchant_id,
                "amount": str(event.amount.amount),
                "currency": str(event.amount.currency)
            }
            payload_json = json.dumps(payload, sort_keys=True)
            
            signature = hmac.new(
                key=config.webhook_secret.encode('utf-8'),
                msg=payload_json.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()

            self._outbox_repo.add(
                merchant_id=event.merchant_id,
                event_type=event_type,
                payload=payload_json,
                signature=signature
            )
            # No explicit commit. The root UoW (e.g., CompleteFundsHandler) will commit this atomically.