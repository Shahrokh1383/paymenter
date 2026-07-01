from abc import ABC, abstractmethod
from typing import List
from src.ledger.application.dto.escrow_account_summary import EscrowAccountSummary

class EscrowAccountQueryPort(ABC):
    @abstractmethod
    def get_all_escrow_summaries(self) -> List[EscrowAccountSummary]: 
        raise NotImplementedError