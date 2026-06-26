from typing import List, Any
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.currency import Currency
from src.identity.domain.repositories import CurrencyRepository

class SqliteCurrencyRepository(CurrencyRepository):
    def __init__(self, uow: UnitOfWork): self._uow = uow

    def add(self, currency: Currency) -> int:
        cursor = self._uow.conn.execute("INSERT INTO currencies (name, code) VALUES (?, ?)", (currency.name, currency.code))
        return cursor.lastrowid

    def update(self, currency: Currency) -> None:
        self._uow.conn.execute("UPDATE currencies SET is_active = ? WHERE id = ?", (currency.is_active, currency.id))

    def toggle_status(self, currency_id: int) -> None:
        self._uow.conn.execute("UPDATE currencies SET is_active = NOT is_active WHERE id = ?", (currency_id,))

    def get_all(self) -> List[Any]: return self._uow.conn.execute("SELECT * FROM currencies").fetchall()
    def get_active(self) -> List[Any]: return self._uow.conn.execute("SELECT * FROM currencies WHERE is_active = 1").fetchall()
    def exists_by_code(self, code: str) -> bool: return self._uow.conn.execute("SELECT id FROM currencies WHERE code = ?", (code,)).fetchone() is not None