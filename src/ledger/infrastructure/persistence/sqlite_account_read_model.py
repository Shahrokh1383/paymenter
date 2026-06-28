from decimal import Decimal
from typing import List

from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.dto.account_summary import AccountSummary
from src.ledger.application.ports.account_query_port import AccountQueryPort

class SqliteAccountReadModel(AccountQueryPort):
    """
    Read-side implementation of AccountQueryPort.
    Adheres to SRP by handling ONLY read queries for account summaries.
    """
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_all_summaries(self) -> List[AccountSummary]:
        rows = self._uow.conn.execute("""
            SELECT 
                a.id, 
                a.user_id, 
                u.name AS user_name, 
                a.currency_id, 
                c.code AS currency_code, 
                a.account_number, 
                a.balance
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            JOIN users u ON a.user_id = u.id
        """).fetchall()

        return [
            AccountSummary(
                id=row['id'],
                user_id=row['user_id'],
                user_name=row['user_name'],
                currency_id=row['currency_id'],
                currency_code=row['currency_code'],
                account_number=row['account_number'],
                balance=Decimal(str(row['balance']))
            )
            for row in rows
        ]