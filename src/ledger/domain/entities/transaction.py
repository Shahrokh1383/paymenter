from dataclasses import dataclass
from src.common.domain.value_objects.money import Money
from src.common.domain.exceptions import InvalidTransactionStateError

@dataclass
class Transaction:
    id: int
    from_account_id: int
    to_account_id: int
    amount: Money
    status: str
    merchant_id: int
    user_email: str

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
    def create_pending(from_account_id: int, to_account_id: int, amount: Money, merchant_id: int, user_email: str) -> 'Transaction':
        """Factory method to create a new valid Pending transaction."""
        return Transaction(
            id=0,  # 0 indicates it hasn't been persisted yet
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            status='Pending',
            merchant_id=merchant_id,
            user_email=user_email
        )