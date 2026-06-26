from decimal import Decimal
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.entities.account import Account
from src.ledger.domain.repositories import AccountRepository
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.ledger.domain.value_objects.card_number import CardNumber
from src.common.domain.value_objects.money import Money

class SqliteAccountRepository(AccountRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_by_id(self, account_id: int) -> Account:
        row = self._uow.conn.execute(
            "SELECT a.*, c.code as currency_code FROM accounts a JOIN currencies c ON a.currency_id = c.id WHERE a.id = ?", 
            (account_id,)
        ).fetchone()
        if not row: return None
        return Account(
            id=row['id'], user_id=row['user_id'],
            account_number=AccountNumber(row['account_number']),
            card_number=CardNumber(row['card_number']),
            balance=Money(Decimal(str(row['balance'])), row['currency_code'])
        )

    def get_by_card_number(self, card_number: CardNumber) -> Account:
        row = self._uow.conn.execute(
            "SELECT a.*, c.code as currency_code FROM accounts a JOIN currencies c ON a.currency_id = c.id WHERE a.card_number = ?", 
            (card_number.value,)
        ).fetchone()
        if not row: return None
        return Account(
            id=row['id'], user_id=row['user_id'],
            account_number=AccountNumber(row['account_number']),
            card_number=CardNumber(row['card_number']),
            balance=Money(Decimal(str(row['balance'])), row['currency_code'])
        )

    def update(self, account: Account) -> None:
        self._uow.conn.execute(
            "UPDATE accounts SET balance = ? WHERE id = ?",
            (float(account.balance.amount), account.id)
        )

    def add(self, account: Account) -> int:
        currency_row = self._uow.conn.execute("SELECT id FROM currencies WHERE code = ?", (account.balance.currency,)).fetchone()
        currency_id = currency_row['id'] if currency_row else 1
        
        cursor = self._uow.conn.execute(
            "INSERT INTO accounts (user_id, currency_id, account_number, card_number, balance) VALUES (?, ?, ?, ?, ?)",
            (account.user_id, currency_id, account.account_number.value, account.card_number.value, float(account.balance.amount))
        )
        return cursor.lastrowid

    def update_currency(self, account_id: int, currency_id: int) -> None:
        self._uow.conn.execute("UPDATE accounts SET currency_id = ? WHERE id = ?", (currency_id, account_id))