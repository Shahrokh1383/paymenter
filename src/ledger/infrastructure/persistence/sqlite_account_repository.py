import sqlite3
from decimal import Decimal
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.domain.repositories import AccountRepository
from src.common.domain.exceptions import ConcurrencyException, CurrencyNotFoundError

class SqliteAccountRepository(AccountRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def _to_cents(self, amount: Decimal) -> int:
        return int(amount * 100)

    def _from_cents(self, cents: int) -> Decimal:
        return Decimal(str(cents)) / Decimal(100)

    def _map_row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row['id'],
            user_id=row['user_id'],
            merchant_id=row['merchant_id'],
            account_number=AccountNumber(row['account_number']),
            balance=Money(self._from_cents(row['balance']), CurrencyCode(row['currency_code'])),
            pending_holds=Money(self._from_cents(row['pending_holds']), CurrencyCode(row['currency_code'])),
            open_authorizations=row['open_authorizations'],
            version=row['version']
        )

    def get_by_id(self, account_id: str) -> Account:
        cursor = self._uow.conn.execute("""
            SELECT a.id, a.user_id, a.merchant_id, a.account_number, a.balance, a.pending_holds, a.open_authorizations, a.version, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.id = ?
        """, (account_id,))
        row = cursor.fetchone()
        if not row: return None
        return self._map_row_to_account(row)

    def update(self, account: Account) -> None:
        currency_row = self._uow.conn.execute(
            "SELECT id FROM currencies WHERE code = ?", (account.balance.currency.value,)
        ).fetchone()
        if not currency_row: 
            raise CurrencyNotFoundError(f"Currency code {account.balance.currency.value} not found.")
            
        cursor = self._uow.conn.execute(
            """UPDATE accounts 
               SET balance = ?, pending_holds = ?, open_authorizations = ?, currency_id = ?, version = version + 1 
               WHERE id = ? AND version = ?""",
            (
                self._to_cents(account.balance.amount), 
                self._to_cents(account.pending_holds.amount), 
                account.open_authorizations, 
                currency_row['id'], 
                account.id, 
                account.version
            )
        )
        if cursor.rowcount == 0: 
            raise ConcurrencyException(f"Optimistic locking conflict while updating account {account.id}.")
        account.version += 1

    def get_by_account_number(self, account_number: str) -> Account:
        cursor = self._uow.conn.execute("""
            SELECT a.id, a.user_id, a.merchant_id, a.account_number, a.balance, a.pending_holds, a.open_authorizations, a.version, c.code as currency_code
            FROM accounts a
            JOIN currencies c ON a.currency_id = c.id
            WHERE a.account_number = ?
        """, (account_number,))
        row = cursor.fetchone()
        if not row: return None
        return self._map_row_to_account(row)

    def add(self, account: Account) -> None:
        currency_row = self._uow.conn.execute(
            "SELECT id FROM currencies WHERE code = ?", (account.balance.currency.value,)
        ).fetchone()
        
        if not currency_row:
            raise CurrencyNotFoundError(f"Currency code {account.balance.currency.value} not found.")
        
        currency_id = currency_row['id']
        
        self._uow.conn.execute(
            """INSERT INTO accounts (id, user_id, merchant_id, currency_id, account_number, balance, pending_holds, open_authorizations, version) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                account.id,
                account.user_id, 
                account.merchant_id, 
                currency_id, 
                account.account_number.value, 
                self._to_cents(account.balance.amount),
                self._to_cents(account.pending_holds.amount),
                account.open_authorizations
            )
        )