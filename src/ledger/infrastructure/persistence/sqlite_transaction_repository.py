import sqlite3
from src.ledger.domain.entities.transaction import Transaction
from src.common.domain.value_objects.money import Money
from src.ledger.domain.repositories import TransactionRepository

class SqliteTransactionRepository(TransactionRepository):
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _map_row_to_txn(self, row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row['id'],
            from_account_id=row['from_account_id'],
            to_account_id=row['to_account_id'],
            amount=Money(str(row['amount']), row['currency_code']),
            status=row['status'],
            merchant_id=row['merchant_id'],
            user_email=row['user_email']
        )

    def get_by_id(self, transaction_id: int) -> Transaction:
        cursor = self.conn.execute("""
            SELECT t.id, t.merchant_id, t.from_account_id, t.to_account_id, 
                   t.amount, t.status, t.user_email, c.code as currency_code
            FROM transactions t
            JOIN currencies c ON t.currency_id = c.id
            WHERE t.id = ?
        """, (transaction_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_txn(row)

    def add(self, transaction: Transaction) -> int:
        cursor = self.conn.execute("""
            INSERT INTO transactions (merchant_id, from_account_id, to_account_id, amount, currency_id, status, user_email)
            VALUES (?, ?, ?, ?, (SELECT id FROM currencies WHERE code = ?), ?, ?)
        """, (
            transaction.merchant_id, 
            transaction.from_account_id, 
            transaction.to_account_id, 
            str(transaction.amount.amount),
            transaction.amount.currency,
            transaction.status,
            transaction.user_email
        ))
        return cursor.lastrowid

    def update(self, transaction: Transaction) -> None:
        self.conn.execute(
            "UPDATE transactions SET status = ? WHERE id = ?",
            (transaction.status, transaction.id)
        )