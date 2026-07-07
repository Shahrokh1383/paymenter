from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher
from src.notifications.domain.ports.idempotency_port import IdempotencyPort
from src.checkout.domain.events.otp_requested_event import OtpRequestedEvent

class OtpNotificationHandler:
    def __init__(self, dispatcher: NotificationDispatcher, idempotency_port: IdempotencyPort):
        self._dispatcher = dispatcher
        self._idempotency_port = idempotency_port

    def handle_otp_requested(self, event: OtpRequestedEvent) -> None:
        # Extract primitive values ONLY at the boundary for the idempotency key
        idempotency_key = f"{type(event).__name__}_{event.session_token.value}_{event.otp_code.value}"
        if self._idempotency_port.is_processed(idempotency_key):
            return

        # Pass Value Objects directly to the Port (Rule 3 compliance)
        self._dispatcher.send_otp(
            to_email=event.registered_email,
            otp_code=event.otp_code.value,
            merchant_name=event.merchant_name,
            amount=event.amount
        )
        self._idempotency_port.mark_as_processed(idempotency_key)