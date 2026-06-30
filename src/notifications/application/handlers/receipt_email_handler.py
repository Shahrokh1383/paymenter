from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher
from src.notifications.domain.ports.merchant_details_port import MerchantDetailsPort
from src.notifications.domain.ports.idempotency_port import IdempotencyPort

# Ledger Events
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)
class ReceiptEmailHandler:
    """Listens to cross-context Domain events and orchestrates the notification dispatch."""
    
    def __init__(self, dispatcher: NotificationDispatcher, merchant_port: MerchantDetailsPort, idempotency_port: IdempotencyPort):
        self._dispatcher = dispatcher
        self._merchant_port = merchant_port
        self._idempotency_port = idempotency_port

    def _generate_idempotency_key(self, event) -> str:
        return f"{type(event).__name__}_{event.transaction_id}"

    # --- Ledger Events ---
    def handle_completed(self, event: TransactionCompletedEvent) -> None:
        self._dispatch_receipt_with_idempotency(event, "Success")

    def handle_failed(self, event: TransactionFailedEvent) -> None:
        self._dispatch_receipt_with_idempotency(event, "Failed")

    def handle_refunded(self, event: TransactionRefundedEvent) -> None:
        self._dispatch_receipt_with_idempotency(event, "Refunded")
        
    def _dispatch_receipt_with_idempotency(self, event, status: str) -> None:
        if not getattr(event, 'user_email', None):
            return 
        
        idempotency_key = self._generate_idempotency_key(event)
        if self._idempotency_port.is_processed(idempotency_key):
            return # Prevent duplicate emails
        
        merchant_name = "Manual Transfer"
        merchant_id = getattr(event, 'merchant_id', None)
        if merchant_id:
            name = self._merchant_port.get_merchant_name(merchant_id)
            if name:
                merchant_name = name

        self._dispatcher.send_receipt(
            to_email=event.user_email,
            status=status,
            amount=event.amount,
            currency_code=event.amount.currency,
            merchant_name=merchant_name
        )
        
        self._idempotency_port.mark_as_processed(idempotency_key)