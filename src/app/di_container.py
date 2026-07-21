from src.common.infrastructure.event_bus import InMemoryEventBus
from src.app.di.identity_di import register_identity
from src.app.di.ledger_di import register_ledger
from src.app.di.notifications_di import register_notifications
from src.app.di.checkout_di import register_checkout
from src.app.di.webhooks_di import register_webhooks

class DIContainer:
    def __init__(self):
        self.event_bus = InMemoryEventBus()
        register_identity(self)
        register_ledger(self)
        register_notifications(self)
        register_checkout(self)
        register_webhooks(self)