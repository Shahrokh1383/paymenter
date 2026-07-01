from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money
from src.ledger.domain.ports.system_account_resolver_port import SystemAccountResolverPort
from src.common.domain.exceptions import AccountNotFoundError

class SqliteSystemAccountResolver(SystemAccountResolverPort):
    """Resolves system accounts by convention-based account numbers (e.g., 'ESCROW_USD')."""
    
    ESCROW_PREFIX = "ESCROW_"

    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_escrow_account(self, currency_code: str) -> Account:
        cursor = self._uow.conn.execute("""
            SELECT a.id, a.user_id, a.account_number, a.balance, a.version, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.user_id = 0 AND c.code = ?
        """, (currency_code,))
        
        row = cursor.fetchone()
        if not row:
            raise AccountNotFoundError(
                f"System Escrow account with number '{self.get_escrow_account}' not found. "
                "Please ensure the database is seeded with system escrow accounts."
            )
            
        return Account(
            id=row['id'],
            user_id=row['user_id'],
            account_number=AccountNumber(row['account_number']),
            balance=Money(str(row['balance']), row['currency_code']),
            version=row['version']
        )