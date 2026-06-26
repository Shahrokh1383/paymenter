from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

@dataclass(frozen=True)
class TransactionCompletedEvent:
    transaction_id: int
    user_email: Optional[str]
    amount: Decimal
    currency_code: str
    merchant_id: Optional[int]

@dataclass(frozen=True)
class TransactionFailedEvent:
    transaction_id: int
    user_email: Optional[str]
    amount: Decimal
    currency_code: str
    merchant_id: Optional[int]

@dataclass(frozen=True)
class TransactionRefundedEvent:
    transaction_id: int
    user_email: Optional[str]
    amount: Decimal
    currency_code: str
    merchant_id: Optional[int]