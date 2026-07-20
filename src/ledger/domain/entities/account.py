from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.common.domain.exceptions import (
    InsufficientFundsError, 
    CurrencyMismatchError, 
    NonZeroBalanceCurrencyChangeError, 
    InvalidTopupAmountError,
    PendingHoldsExistError
)
from src.ledger.domain.value_objects.account_number import AccountNumber

@dataclass
class Account:
    id: str
    user_id: Optional[int]
    merchant_id: Optional[int]
    account_number: AccountNumber
    balance: Money
    pending_holds: Money
    open_authorizations: int
    version: int = 0

    def withdraw(self, amount: Money) -> None:
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match transaction amount currency.")
        if self.balance.amount < amount.amount:
            raise InsufficientFundsError("Insufficient balance in the source account.")
        self.balance = self.balance - amount

    def deposit(self, amount: Money) -> None:
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
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match transaction amount currency.")
        self.balance = self.balance - amount

    def increase_holds(self, amount: Money) -> None:
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match hold amount currency.")
        self.pending_holds = self.pending_holds + amount

    def decrease_holds(self, amount: Money) -> None:
        if self.balance.currency != amount.currency:
            raise CurrencyMismatchError("Account currency does not match hold amount currency.")
        new_holds_amount = max(Decimal('0.00'), self.pending_holds.amount - amount.amount)
        self.pending_holds = Money(new_holds_amount, self.balance.currency)

    def can_change_currency(self) -> bool:
        return (
            self.balance.amount == 0 
            and self.pending_holds.amount == 0 
            and self.open_authorizations == 0
        )

    def change_currency(self, new_currency_code: CurrencyCode) -> None:
        """Changes the account's currency. Enforces zero-balance and zero-holds invariant (BR-3 Fix)."""
        if self.balance.amount != 0:
            raise NonZeroBalanceCurrencyChangeError("Cannot change currency on an account with a balance > 0.")
        
        if self.pending_holds.amount != 0 or self.open_authorizations != 0:
            raise PendingHoldsExistError("Cannot change currency on an account with pending holds or authorizations.")
            
        self.balance = Money(self.balance.amount, new_currency_code)
        self.pending_holds = Money(self.pending_holds.amount, new_currency_code)