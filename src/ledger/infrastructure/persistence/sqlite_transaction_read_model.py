from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.ports.transaction_query_port import TransactionQueryPort
from src.ledger.application.dto.transaction_list_item import TransactionListItem


class SqliteTransactionReadModel(TransactionQueryPort):
    """
    Read-side implementation of TransactionQueryPort.
    Uses UnitOfWork to respect the Dependency Rule (Rule 1).
    """
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_all_summaries(self, status: Optional[str] = None) -> List[TransactionListItem]:
        sql = """
            SELECT t.id, t.amount, t.status, t.created_at, t.user_email,
                   from_acc.account_number as from_account,
                   to_acc.account_number as to_account,
                   c.code as currency_code
            FROM transactions t
            LEFT JOIN accounts from_acc ON t.from_account_id = from_acc.id
            LEFT JOIN accounts to_acc ON t.to_account_id = to_acc.id
            LEFT JOIN currencies c ON t.currency_id = c.id
        """
        params = []
        if status:
            sql += " WHERE t.status = ?"
            params.append(status)
        
        sql += " ORDER BY t.created_at DESC"
        rows = self._uow.conn.execute(sql, params).fetchall()
        
        return [
            TransactionListItem(
                id=row['id'],
                amount=Decimal(str(row['amount'])), # Rule 3: No Primitive Obsession
                currency_code=row['currency_code'],
                status=row['status'],
                created_at=datetime.fromisoformat(row['created_at']) if isinstance(row['created_at'], str) else row['created_at'],
                user_email=row['user_email'],
                from_account_number=row['from_account'],
                to_account_number=row['to_account']
            )
            for row in rows
        ]