from dataclasses import dataclass
from src.common.domain.value_objects.money import Money
from src.common.domain.exceptions import InsufficientFundsError, CurrencyMismatchError
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.ledger.domain.value_objects.card_number import CardNumber

@dataclass
class Account:
    id: int
    user_id: int
    account_number: AccountNumber
    card_number: CardNumber
    balance: Money

    def withdraw(self, amount: Money) -> None:
        """Withdraws funds, enforcing the non-negative balance invariant."""
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match transaction amount currency.")
        
        if self.balance.amount < amount.amount:
            raise InsufficientFundsError("Insufficient balance in the source account.")
            
        self.balance = self.balance - amount

    def deposit(self, amount: Money) -> None:
        """Deposits funds into the account."""
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match transaction amount currency.")
            
        self.balance = self.balance + amount