from dataclasses import dataclass
from typing import Optional
from src.common.domain.value_objects.money import Money

@dataclass(frozen=True)
class TransactionCompletedEvent:
    transaction_id: str
    payer_account_id: str
    amount: Money
    merchant_id: Optional[int]

@dataclass(frozen=True)
class TransactionFailedEvent:
    transaction_id: str
    payer_account_id: str
    amount: Money
    merchant_id: Optional[int]

@dataclass(frozen=True)
class TransactionRefundedEvent:
    transaction_id: str
    payer_account_id: str
    amount: Money
    merchant_id: Optional[int]