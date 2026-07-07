from abc import ABC, abstractmethod
from typing import List, Optional, Any
from src.identity.domain.entities.user import User
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.value_objects.api_key import ApiKey

class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> int: raise NotImplementedError
    
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: raise NotImplementedError
    
    @abstractmethod
    def search_summaries(self, query: str) -> List[Any]: raise NotImplementedError
    
    @abstractmethod
    def exists_by_phone_email(self, phone_email: str) -> bool: raise NotImplementedError

class MerchantRepository(ABC):
    @abstractmethod
    def add(self, merchant: Merchant) -> int: raise NotImplementedError
    
    @abstractmethod
    def update(self, merchant: Merchant) -> None: raise NotImplementedError
    
    @abstractmethod
    def get_by_id(self, merchant_id: int) -> Optional[Merchant]: raise NotImplementedError
    
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: raise NotImplementedError
    
    @abstractmethod
    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]: raise NotImplementedError