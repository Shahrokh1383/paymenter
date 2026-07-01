from decimal import Decimal
from typing import List

from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.dto.escrow_account_summary import EscrowAccountSummary
from src.ledger.application.ports.escrow_account_query_port import EscrowAccountQueryPort

class SqliteEscrowAccountReadModel(EscrowAccountQueryPort):
    """
    Read-side implementation for System Escrow accounts.
    Adheres to SRP by strictly isolating system ledger accounts from user accounts.
    """
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_all_escrow_summaries(self) -> List[EscrowAccountSummary]:
        rows = self._uow.conn.execute("""
            SELECT 
                a.id, 
                a.currency_id, 
                c.code AS currency_code, 
                a.account_number, 
                a.balance
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.user_id IS NULL
        """).fetchall()

        return [
            EscrowAccountSummary(
                id=row['id'],
                currency_id=row['currency_id'],
                currency_code=row['currency_code'],
                account_number=row['account_number'],
                balance=Decimal(str(row['balance']))
            )
            for row in rows
        ]