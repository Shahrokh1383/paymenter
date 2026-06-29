from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher
from src.notifications.domain.ports.merchant_details_port import MerchantDetailsPort
from src.notifications.domain.ports.idempotency_port import IdempotencyPort

# Ledger Events
from src.ledger.domain.events.transaction_events import (
    TransactionCompletedEvent, TransactionFailedEvent, TransactionRefundedEvent
)
# Checkout Events
from src.checkout.domain.events.payment_initiated_event import PaymentInitiatedEvent

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
        
    # --- Checkout Events ---
    def handle_initiated(self, event: PaymentInitiatedEvent) -> None:
        """Dispatches the OTP email when a payment session is initiated in the Checkout context."""
        idempotency_key = f"{type(event).__name__}_{event.token}" # Assuming token is unique
        if self._idempotency_port.is_processed(idempotency_key):
            return

        self._dispatcher.send_otp(
            to_email=event.user_email,
            otp_code=event.otp_code,
            merchant_name=event.merchant_name,
            amount=event.amount,
            currency_code=event.currency_code
        )
        self._idempotency_port.mark_as_processed(idempotency_key)

    def _dispatch_receipt_with_idempotency(self, event, status: str) -> None:
        if not event.user_email:
            return 
        
        idempotency_key = self._generate_idempotency_key(event)
        if self._idempotency_port.is_processed(idempotency_key):
            return # Prevent duplicate emails
        
        merchant_name = "Manual Transfer"
        if event.merchant_id:
            name = self._merchant_port.get_merchant_name(event.merchant_id)
            if name:
                merchant_name = name

        self._dispatcher.send_receipt(
            to_email=event.user_email,
            status=status,
            amount=event.amount,
            currency_code=event.amount.currency, # Redundant but kept for adapter signature compatibility
            merchant_name=merchant_name
        )
        
        self._idempotency_port.mark_as_processed(idempotency_key)