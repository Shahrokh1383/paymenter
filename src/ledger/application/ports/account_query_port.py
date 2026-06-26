from abc import ABC, abstractmethod
from typing import List
from src.ledger.application.dto.account_summary import AccountSummary

class AccountQueryPort(ABC):
    @abstractmethod
    def get_all_summaries(self) -> List[AccountSummary]: raise NotImplementedError