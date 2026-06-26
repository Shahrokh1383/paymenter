from typing import Any, List, Callable, Dict
from src.common.domain.ports.event_bus import EventBus

class InMemoryEventBus(EventBus):
    """Synchronous in-memory implementation of the EventBus."""
    
    def __init__(self):
        self._subscribers: Dict[type, List[Callable]] = {}

    def subscribe(self, event_type: type, handler: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        event_type = type(event)
        for handler in self._subscribers.get(event_type, []):
            handler(event)