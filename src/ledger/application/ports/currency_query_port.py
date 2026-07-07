from abc import ABC, abstractmethod
from typing import List
from src.ledger.application.dto.currency_summary import CurrencySummaryDTO

class CurrencyQueryPort(ABC):
    @abstractmethod
    def get_all(self) -> List[CurrencySummaryDTO]: pass
    
    @abstractmethod
    def get_active(self) -> List[CurrencySummaryDTO]: pass