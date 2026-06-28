import sqlite3
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money
from src.ledger.domain.repositories import AccountRepository
# FIX TD-2: Removed CardNumber import

class SqliteAccountRepository(AccountRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def _map_row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row['id'],
            user_id=row['user_id'],
            account_number=AccountNumber(row['account_number']),
            # FIX TD-2: Stopped mapping card_number from DB to Domain entity
            balance=Money(str(row['balance']), row['currency_code'])
        )

    def get_by_id(self, account_id: int) -> Account:
        # FIX TD-2: Removed a.card_number from SELECT statement (Least Privilege at DB level)
        cursor = self._uow.conn.execute("""
            SELECT a.id, a.user_id, a.account_number, a.balance, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.id = ?
        """, (account_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_account(row)

    # FIX TD-2: Deleted get_by_card_number() implementation entirely.

    def update(self, account: Account) -> None:
        self._uow.conn.execute(
            "UPDATE accounts SET balance = ? WHERE id = ?",
            (str(account.balance.amount), account.id)
        )

    def add(self, account: Account) -> int:
        currency_row = self._uow.conn.execute("SELECT id FROM currencies WHERE code = ?", (account.balance.currency,)).fetchone()
        currency_id = currency_row['id'] if currency_row else 1
        
        cursor = self._uow.conn.execute(
            "INSERT INTO accounts (user_id, currency_id, account_number, card_number, balance) VALUES (?, ?, ?, ?, ?)",
            (account.user_id, currency_id, account.account_number.value, "", str(account.balance.amount))
        )
        return cursor.lastrowid