from src.common.infrastructure.event_bus import InMemoryEventBus

# Import Context Registration Modules
from src.app.di.ledger_di import register_ledger
from src.app.di.notifications_di import register_notifications
from src.app.di.checkout_di import register_checkout

class DIContainer:
    """
    Centralized Dependency Injection Container.
    Manages global singletons and delegates context-specific wiring 
    """
    def __init__(self):
        self.event_bus = InMemoryEventBus()
        
        # Register Bounded Context modules
        register_ledger(self)
        register_notifications(self)
        register_checkout(self)