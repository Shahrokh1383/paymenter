from abc import ABC, abstractmethod

class CurrencyQueryPort(ABC):
    """
    Port to resolve currency identifiers to ISO codes.
    """
    @abstractmethod
    def get_currency_code_by_id(self, currency_id: int) -> str:
        pass