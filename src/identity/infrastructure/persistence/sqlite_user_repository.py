from typing import List, Any
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.user import User
from src.identity.domain.repositories import UserRepository

class SqliteUserRepository(UserRepository):
    def __init__(self, uow: UnitOfWork): self._uow = uow

    def add(self, user: User) -> int:
        cursor = self._uow.conn.execute("INSERT INTO users (name, phone_email) VALUES (?, ?)", (user.name, user.phone_email))
        return cursor.lastrowid

    def get_all_summaries(self) -> List[Any]:
        return self._uow.conn.execute("""
            SELECT u.id, u.name, u.phone_email, a.id as account_id, a.account_number, a.card_number, a.balance, c.code as currency_code
            FROM users u LEFT JOIN accounts a ON u.id = a.user_id LEFT JOIN currencies c ON a.currency_id = c.id
        """).fetchall()

    def search_summaries(self, query: str) -> List[Any]:
        like = f"%{query}%"
        return self._uow.conn.execute("""
            SELECT u.id, u.name, u.phone_email, a.id as account_id, a.account_number, a.card_number, a.balance, c.code as currency_code
            FROM users u LEFT JOIN accounts a ON u.id = a.user_id LEFT JOIN currencies c ON a.currency_id = c.id
            WHERE u.name LIKE ? OR a.account_number LIKE ? OR a.card_number LIKE ?
        """, (like, like, like)).fetchall()