from abc import ABC, abstractmethod

class IdempotencyPort(ABC):
    """Port for ensuring event handlers are idempotent."""
    
    @abstractmethod
    def is_processed(self, event_id: str) -> bool:
        """Check if an event has already been processed."""
        pass

    @abstractmethod
    def mark_as_processed(self, event_id: str) -> None:
        """Record that an event has been successfully processed."""
        pass