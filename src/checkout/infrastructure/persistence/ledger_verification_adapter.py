from typing import Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.checkout.domain.ports.transaction_verification_port import TransactionVerificationPort, TransactionStatus

class LedgerVerificationAdapter(TransactionVerificationPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_transaction_status(self, transaction_id: int) -> Optional[TransactionStatus]:
        row = self._uow.conn.execute("""
            SELECT t.id, t.status, t.amount, c.code as currency_code
            FROM transactions t
            JOIN currencies c ON t.currency_id = c.id
            WHERE t.id = ?
        """, (transaction_id,)).fetchone()
        
        if not row:
            return None
            
        return TransactionStatus(
            transaction_id=row['id'],
            status=row['status'],
            amount=float(row['amount']),
            currency_code=row['currency_code']
        )