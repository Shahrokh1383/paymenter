from abc import ABC, abstractmethod

class CurrencyCommandPort(ABC):
    """Port for writing currency data."""
    
    @abstractmethod
    def add_currency(self, name: str, code: str) -> int:
        """Inserts a new currency and returns its ID."""
        pass