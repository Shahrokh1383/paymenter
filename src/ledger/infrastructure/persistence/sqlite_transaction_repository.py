import sqlite3
from decimal import Decimal
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.transaction import Transaction
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.domain.repositories import TransactionRepository
from src.common.domain.exceptions import ConcurrencyException

class SqliteTransactionRepository(TransactionRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def _to_cents(self, amount: Decimal) -> int:
        return int(amount * 100)

    def _from_cents(self, cents: int) -> Decimal:
        return Decimal(str(cents)) / Decimal(100)

    def _map_row_to_txn(self, row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row['id'],
            from_account_id=row['from_account_id'],
            to_account_id=row['to_account_id'],
            amount=Money(self._from_cents(row['amount']), CurrencyCode(row['currency_code'])),
            status=row['status'],
            merchant_id=row['merchant_id'],
            user_email=row['user_email'],
            version=row['version']
        )

    def get_by_id(self, transaction_id: str) -> Transaction:
        cursor = self._uow.conn.execute("""
            SELECT t.id, t.merchant_id, t.from_account_id, t.to_account_id, 
                   t.amount, t.status, t.user_email, t.version, c.code as currency_code
            FROM transactions t
            JOIN currencies c ON t.currency_id = c.id
            WHERE t.id = ?
        """, (transaction_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_txn(row)

    def add(self, transaction: Transaction) -> None:
        self._uow.conn.execute("""
            INSERT INTO transactions (id, merchant_id, from_account_id, to_account_id, amount, currency_id, status, user_email, version)
            VALUES (?, ?, ?, ?, ?, (SELECT id FROM currencies WHERE code = ?), ?, ?, 0)
        """, (
            transaction.id,
            transaction.merchant_id, 
            transaction.from_account_id, 
            transaction.to_account_id, 
            self._to_cents(transaction.amount.amount),
            transaction.amount.currency.value,
            transaction.status,
            transaction.user_email
        ))

    def update(self, transaction: Transaction) -> None:
        cursor = self._uow.conn.execute(
            "UPDATE transactions SET status = ?, version = version + 1 WHERE id = ? AND version = ?",
            (transaction.status, transaction.id, transaction.version)
        )
        
        if cursor.rowcount == 0:
            raise ConcurrencyException(f"Optimistic locking conflict while updating transaction {transaction.id}.")
            
        transaction.version += 1