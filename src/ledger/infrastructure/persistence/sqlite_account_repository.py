import sqlite3
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.ledger.domain.value_objects.card_number import CardNumber
from src.common.domain.value_objects.money import Money
from src.ledger.domain.repositories import AccountRepository

class SqliteAccountRepository(AccountRepository):
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _map_row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row['id'],
            user_id=row['user_id'],
            account_number=AccountNumber(row['account_number']),
            card_number=CardNumber(row['card_number']),
            balance=Money(str(row['balance']), row['currency_code']) # Assuming currency_code is joined in query
        )

    def get_by_id(self, account_id: int) -> Account:
        cursor = self.conn.execute("""
            SELECT a.id, a.user_id, a.account_number, a.card_number, a.balance, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.id = ?
        """, (account_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_account(row)

    def get_by_card_number(self, card_number: CardNumber) -> Account:
        cursor = self.conn.execute("""
            SELECT a.id, a.user_id, a.account_number, a.card_number, a.balance, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.card_number = ?
        """, (card_number.value,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_account(row)

    def update(self, account: Account) -> None:
        self.conn.execute(
            "UPDATE accounts SET balance = ? WHERE id = ?",
            (str(account.balance.amount), account.id)
        )

    def add(self, account: Account) -> int:
        # Implementation for adding new accounts (used later by identity context)
        pass 