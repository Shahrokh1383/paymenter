from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.domain.ports.system_account_resolver_port import SystemAccountResolverPort
from src.common.domain.exceptions import AccountNotFoundError

class SqliteSystemAccountResolver(SystemAccountResolverPort):
    """Resolves system accounts by database conventions (user_id IS NULL AND merchant_id IS NULL)."""
    
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_escrow_account(self, currency: CurrencyCode) -> Account:
        cursor = self._uow.conn.execute("""
            SELECT a.id, a.user_id, a.merchant_id, a.account_number, a.balance, a.version, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.user_id IS NULL AND a.merchant_id IS NULL AND c.code = ?
        """, (currency.value,))
        
        row = cursor.fetchone()
        if not row:
            raise AccountNotFoundError(
                f"System Escrow account for currency '{currency.value}' not found. "
                "Please ensure the currency is added via the dashboard first."
            )
            
        return Account(
            id=row['id'],
            user_id=row['user_id'],
            merchant_id=row['merchant_id'],
            account_number=AccountNumber(row['account_number']),
            balance=Money(str(row['balance']), CurrencyCode(row['currency_code'])),
            version=row['version']
        )