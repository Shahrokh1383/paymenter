from abc import ABC, abstractmethod
from typing import List, Optional
from src.ledger.application.dto.transaction_list_item import TransactionListItem

class TransactionQueryPort(ABC):
    @abstractmethod
    def get_all_summaries(self, status: Optional[str] = None) -> List[TransactionListItem]:
        raise NotImplementedError