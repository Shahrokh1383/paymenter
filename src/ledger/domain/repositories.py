from abc import ABC, abstractmethod
from src.ledger.domain.entities.account import Account
from src.ledger.domain.entities.transaction import Transaction

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