import uuid
from dataclasses import dataclass
from typing import Optional
from src.common.domain.value_objects.money import Money
from src.common.domain.exceptions import InvalidTransactionStateError

@dataclass
class Transaction:
    id: str
    from_account_id: str
    to_account_id: str
    amount: Money
    status: str
    merchant_id: Optional[int]
    user_email: Optional[str]
    version: int = 0

    def mark_as_success(self) -> None:
        if self.status != 'Pending':
            raise InvalidTransactionStateError(f"Transaction cannot be completed. Current status: {self.status}")
        self.status = 'Success'

    def mark_as_failed(self) -> None:
        if self.status != 'Pending':
            raise InvalidTransactionStateError(f"Transaction cannot be failed. Current status: {self.status}")
        self.status = 'Failed'

    def mark_as_refunded(self) -> None:
        if self.status != 'Success':
            raise InvalidTransactionStateError(f"Transaction cannot be refunded. Current status: {self.status}")
        self.status = 'Refunded'

    @staticmethod
    def create_pending(from_account_id: str, to_account_id: str, amount: Money, merchant_id: Optional[int], user_email: Optional[str]) -> 'Transaction':
        """Factory method to create a new valid Pending transaction."""
        return Transaction(
            id=uuid.uuid4().hex,  
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            status='Pending',
            merchant_id=merchant_id,
            user_email=user_email
        )