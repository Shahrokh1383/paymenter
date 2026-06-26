from abc import ABC, abstractmethod
from typing import List, Optional, Any
from src.identity.domain.entities.user import User
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.entities.currency import Currency
from src.identity.domain.value_objects.api_key import ApiKey

class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> int: raise NotImplementedError
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: raise NotImplementedError
    @abstractmethod
    def search_summaries(self, query: str) -> List[Any]: raise NotImplementedError

class MerchantRepository(ABC):
    @abstractmethod
    def add(self, merchant: Merchant) -> int: raise NotImplementedError
    @abstractmethod
    def update(self, merchant: Merchant) -> None: raise NotImplementedError
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: raise NotImplementedError
    @abstractmethod
    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]: raise NotImplementedError

class CurrencyRepository(ABC):
    @abstractmethod
    def add(self, currency: Currency) -> int: raise NotImplementedError
    @abstractmethod
    def update(self, currency: Currency) -> None: raise NotImplementedError
    @abstractmethod
    def get_all(self) -> List[Currency]: raise NotImplementedError
    @abstractmethod
    def get_active(self) -> List[Currency]: raise NotImplementedError
    @abstractmethod
    def exists_by_code(self, code: str) -> bool: raise NotImplementedError