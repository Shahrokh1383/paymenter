from dataclasses import dataclass
from typing import Optional
from src.common.domain.value_objects.money import Money
from src.common.domain.exceptions import (
    InsufficientFundsError, 
    CurrencyMismatchError, 
    NonZeroBalanceCurrencyChangeError, 
    InvalidTopupAmountError
)
from src.ledger.domain.value_objects.account_number import AccountNumber

@dataclass
class Account:
    id: int
    user_id: Optional[int]
    merchant_id: Optional[int]
    account_number: AccountNumber
    balance: Money
    version: int = 0

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
    
    def topup(self, amount: Money) -> None:
        if amount.amount <= 0:
            raise InvalidTopupAmountError("Topup amount must be greater than zero.")
            
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match topup amount currency.")
            
        self.balance = self.balance + amount

    def apply_system_reversal(self, amount: Money) -> None:
        """
        Forces a debit for system-initiated refunds (Chargebacks).
        Bypasses non-negative balance invariant to prevent TD-8 crashes when receiver has spent funds.
        """
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match transaction amount currency.")
            
        self.balance = self.balance - amount

    def can_change_currency(self) -> bool:
        return self.balance.amount == 0

    def change_currency(self, new_currency_code: str) -> None:
        """Changes the account's currency. Enforces zero-balance invariant (BR-5)."""
        if not self.can_change_currency():
            raise NonZeroBalanceCurrencyChangeError("Cannot change currency on an account with a balance > 0.")
        self.balance = Money(self.balance.amount, new_currency_code)