from typing import Optional
from src.notifications.domain.ports.account_owner_resolver_port import AccountOwnerResolverPort
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

class SqliteAccountOwnerAdapter(AccountOwnerResolverPort):
    """Resolves the Paymenter user email linked to a specific Ledger account."""
    
    def get_email_by_account_id(self, account_id: int) -> Optional[str]:
        uow = SqliteUnitOfWork()
        with uow:
            row = uow.conn.execute("""
                SELECT u.phone_email 
                FROM accounts a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = ?
            """, (account_id,)).fetchone()
            return row['phone_email'] if row else None