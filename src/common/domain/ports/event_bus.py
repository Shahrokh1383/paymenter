from abc import ABC, abstractmethod
from typing import Any, Callable

class EventBus(ABC):
    """Port for publishing and subscribing to Domain Events."""
    
    @abstractmethod
    def subscribe(self, event_type: type, handler: Callable) -> None:
        raise NotImplementedError

    @abstractmethod
    def publish(self, event: Any) -> None:
        raise NotImplementedError