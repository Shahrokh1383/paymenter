import sqlite3
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money
from src.ledger.domain.repositories import AccountRepository
from src.common.domain.exceptions import ConcurrencyException

class SqliteAccountRepository(AccountRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def _map_row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row['id'],
            user_id=row['user_id'],
            account_number=AccountNumber(row['account_number']),
            balance=Money(str(row['balance']), row['currency_code']),
            version=row['version']
        )

    def get_by_id(self, account_id: int) -> Account:
        cursor = self._uow.conn.execute("""
            SELECT a.id, a.user_id, a.account_number, a.balance, a.version, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.id = ?
        """, (account_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_account(row)

    def update(self, account: Account) -> None:
        currency_row = self._uow.conn.execute(
            "SELECT id FROM currencies WHERE code = ?", 
            (account.balance.currency,)
        ).fetchone()
        
        if not currency_row:
            raise ValueError(f"Currency code {account.balance.currency} not found in database.")
            
        cursor = self._uow.conn.execute(
            "UPDATE accounts SET balance = ?, currency_id = ?, version = version + 1 WHERE id = ? AND version = ?",
            (str(account.balance.amount), currency_row['id'], account.id, account.version)
        )
        
        if cursor.rowcount == 0:
            raise ConcurrencyException(f"Optimistic locking conflict while updating account {account.id}.")
            
        # Synchronize in-memory aggregate state
        account.version += 1

    def add(self, account: Account) -> int:
        currency_row = self._uow.conn.execute("SELECT id FROM currencies WHERE code = ?", (account.balance.currency,)).fetchone()
        currency_id = currency_row['id'] if currency_row else 1
        
        cursor = self._uow.conn.execute(
            "INSERT INTO accounts (user_id, currency_id, account_number, balance) VALUES (?, ?, ?, ?)",
            (account.user_id, currency_id, account.account_number.value, str(account.balance.amount))
        )
        return cursor.lastrowid