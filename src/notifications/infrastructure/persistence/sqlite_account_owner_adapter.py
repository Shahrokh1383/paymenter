from typing import Optional
from src.notifications.domain.ports.account_owner_resolver_port import AccountOwnerResolverPort
from src.notifications.domain.value_objects.account_owner_profile import AccountOwnerProfile
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode

class SqliteAccountOwnerAdapter(AccountOwnerResolverPort):
    """Resolves the Paymenter user profile linked to a specific Ledger account."""
    
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

    def resolve_profile_by_account_id(self, account_id: int) -> Optional[AccountOwnerProfile]:
        uow = SqliteUnitOfWork()
        with uow:
            row = uow.conn.execute("""
                SELECT u.phone_email, a.balance, c.code as currency_code
                FROM accounts a
                JOIN users u ON a.user_id = u.id
                JOIN currencies c ON a.currency_id = c.id
                WHERE a.id = ?
            """, (account_id,)).fetchone()
            
            if not row:
                return None
                
            email = row['phone_email']
            balance_amount = str(row['balance'])
            currency_code = row['currency_code']
            
            money_vo = Money(balance_amount, CurrencyCode(currency_code))
            return AccountOwnerProfile(email=email, balance=money_vo)