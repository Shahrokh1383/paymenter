from decimal import Decimal
from typing import List
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.dto.account_summary import AccountSummary
from src.ledger.application.ports.account_query_port import AccountQueryPort

class SqliteAccountReadModel(AccountQueryPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_all_summaries(self) -> List[AccountSummary]:
        rows = self._uow.conn.execute("""
            SELECT 
                a.id, a.user_id, 
                COALESCE(u.name, m.name, 'System') AS user_name,
                a.currency_id, c.code AS currency_code, 
                a.account_number, a.pending_holds, a.open_authorizations, a.balance
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            LEFT JOIN users u ON a.user_id = u.id
            LEFT JOIN merchants m ON a.merchant_id = m.id
            WHERE a.user_id IS NOT NULL OR a.merchant_id IS NOT NULL
        """).fetchall()

        return [
            AccountSummary(
                id=row['id'], 
                user_id=row['user_id'] or 0, 
                user_name=row['user_name'],
                currency_id=row['currency_id'], 
                currency_code=row['currency_code'],
                account_number=row['account_number'], 
                card_number=None,
                pending_holds=Decimal(str(row['pending_holds'])) / Decimal(100),
                open_authorizations=row['open_authorizations'],
                balance=Decimal(str(row['balance'])) / Decimal(100)
            ) for row in rows
        ]