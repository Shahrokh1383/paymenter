from abc import ABC, abstractmethod
from typing import Optional

class AccountLookupPort(ABC):
    @abstractmethod
    def get_account_id_by_card_number(self, card_number: str) -> Optional[int]:
        raise NotImplementedError

    @abstractmethod
    def get_settlement_account_id(self, merchant_id: int, currency_code: str) -> Optional[int]:
        raise NotImplementedError

    @abstractmethod
    def get_email_by_card_number(self, card_number: str) -> Optional[str]:
        raise NotImplementedError