from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher
from src.notifications.domain.ports.merchant_details_port import MerchantDetailsPort

# Ledger Events
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)
# Checkout Events
from src.checkout.domain.events.payment_initiated_event import PaymentInitiatedEvent

class ReceiptEmailHandler:
    """Listens to cross-context Domain events and orchestrates the notification dispatch."""
    
    def __init__(self, dispatcher: NotificationDispatcher, merchant_port: MerchantDetailsPort):
        self._dispatcher = dispatcher
        self._merchant_port = merchant_port

    # --- Ledger Events ---
    def handle_completed(self, event: TransactionCompletedEvent) -> None:
        self._dispatch_receipt(event, "Success")

    def handle_failed(self, event: TransactionFailedEvent) -> None:
        self._dispatch_receipt(event, "Failed")

    def handle_refunded(self, event: TransactionRefundedEvent) -> None:
        self._dispatch_receipt(event, "Refunded")
        
    # --- Checkout Events ---
    def handle_initiated(self, event: PaymentInitiatedEvent) -> None:
        """Dispatches the OTP email when a payment session is initiated in the Checkout context."""
        self._dispatcher.send_otp(
            to_email=event.user_email,
            otp_code=event.otp_code,
            merchant_name=event.merchant_name,
            amount=float(event.amount),
            currency_code=event.currency_code
        )

    def _dispatch_receipt(self, event, status: str) -> None:
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