from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher
from src.notifications.domain.ports.merchant_details_port import MerchantDetailsPort
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)

class ReceiptEmailHandler:
    """Listens to Ledger events and orchestrates the notification dispatch."""
    
    def __init__(self, dispatcher: NotificationDispatcher, merchant_port: MerchantDetailsPort):
        self._dispatcher = dispatcher
        self._merchant_port = merchant_port

    def handle_completed(self, event: TransactionCompletedEvent) -> None:
        self._dispatch(event, "Success")

    def handle_failed(self, event: TransactionFailedEvent) -> None:
        self._dispatch(event, "Failed")

    def handle_refunded(self, event: TransactionRefundedEvent) -> None:
        self._dispatch(event, "Refunded")

    def _dispatch(self, event, status: str) -> None:
        if not event.user_email:
            return # Cannot send email without an address
        
        merchant_name = "Manual Transfer"
        if event.merchant_id:
            name = self._merchant_port.get_merchant_name(event.merchant_id)
            if name:
                merchant_name = name

        self._dispatcher.send_receipt(
            to_email=event.user_email,
            status=status,
            amount=float(event.amount),
            currency_code=event.currency_code,
            merchant_name=merchant_name
        )