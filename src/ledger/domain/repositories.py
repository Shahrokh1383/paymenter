from abc import ABC, abstractmethod
from typing import Optional
from src.ledger.domain.entities.account import Account
from src.ledger.domain.entities.transaction import Transaction
from src.ledger.domain.entities.currency import Currency
from src.common.domain.value_objects.currency_code import CurrencyCode

class AccountRepository(ABC):
    @abstractmethod
    def get_by_id(self, account_id: int) -> Account: pass

    @abstractmethod
    def get_by_account_number(self, account_number: str) -> Account: pass
    
    @abstractmethod
    def update(self, account: Account) -> None: pass
    
    @abstractmethod
    def add(self, account: Account) -> int: pass

class TransactionRepository(ABC):
    @abstractmethod
    def get_by_id(self, transaction_id: int) -> Transaction: pass
    
    @abstractmethod
    def add(self, transaction: Transaction) -> int: pass
    
    @abstractmethod
    def update(self, transaction: Transaction) -> None: pass

class CurrencyRepository(ABC):
    @abstractmethod
    def get_by_id(self, currency_id: int) -> Optional[Currency]: pass
    
    @abstractmethod
    def get_by_code(self, code: CurrencyCode) -> Optional[Currency]: pass
    
    @abstractmethod
    def add(self, currency: Currency) -> int: pass
    
    @abstractmethod
    def update(self, currency: Currency) -> None: pass