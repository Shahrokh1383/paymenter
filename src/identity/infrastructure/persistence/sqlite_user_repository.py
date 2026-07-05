import sqlite3
from typing import List, Any
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.user import User
from src.identity.domain.value_objects.phone_email import PhoneEmail
from src.identity.domain.repositories import UserRepository
from src.common.domain.exceptions import UserAlreadyExistsError
from src.identity.application.dto.user_summary import UserSummaryDTO

class SqliteUserRepository(UserRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def add(self, user: User) -> int:
        try:
            cursor = self._uow.conn.execute(
                "INSERT INTO users (name, phone_email) VALUES (?, ?)",
                (user.name, str(user.phone_email))
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.phone_email" in str(e):
                raise UserAlreadyExistsError(f"User with {user.phone_email} already exists.")
            raise

    def exists_by_phone_email(self, phone_email: str) -> bool:
        row = self._uow.conn.execute(
            "SELECT id FROM users WHERE phone_email = ?", (phone_email,)
        ).fetchone()
        return row is not None

    def get_all_summaries(self) -> List[UserSummaryDTO]:
        rows = self._uow.conn.execute(
            "SELECT user_id, name, phone_email, account_id, account_number, card_number, balance, currency_code FROM user_summaries"
        ).fetchall()
        return [UserSummaryDTO(
            user_id=r['user_id'],
            name=r['name'],
            phone_email=r['phone_email'],
            account_id=r['account_id'],
            account_number=r['account_number'],
            card_number=r['card_number'],
            balance=str(r['balance']),
            currency_code=r['currency_code']
        ) for r in rows]
    
    def exists_by_id(self, user_id: int) -> bool:
        cursor = self._uow.conn.execute("SELECT 1 FROM users WHERE id = ?",(user_id,))
        return cursor.fetchone() is not None

    def search_summaries(self, query: str) -> List[UserSummaryDTO]:
        like = f"%{query}%"
        rows = self._uow.conn.execute(
            """SELECT user_id, name, phone_email, account_id, account_number, card_number, balance, currency_code
               FROM user_summaries
               WHERE name LIKE ? OR account_number LIKE ? OR card_number LIKE ?""",
            (like, like, like)
        ).fetchall()
        return [UserSummaryDTO(
            user_id=r['user_id'],
            name=r['name'],
            phone_email=r['phone_email'],
            account_id=r['account_id'],
            account_number=r['account_number'],
            card_number=r['card_number'],
            balance=str(r['balance']),
            currency_code=r['currency_code']
        ) for r in rows]