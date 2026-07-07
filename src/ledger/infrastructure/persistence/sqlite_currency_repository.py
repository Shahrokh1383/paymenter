from typing import Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.domain.entities.currency import Currency
from src.ledger.domain.repositories import CurrencyRepository

class SqliteCurrencyRepository(CurrencyRepository):
    """SQLite implementation for Currency Aggregate persistence."""
    
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def add(self, currency: Currency) -> int:
        cursor = self._uow.conn.execute(
            "INSERT INTO currencies (name, code, is_active) VALUES (?, ?, ?)",
            (currency.name, currency.code.value, int(currency.is_active))
        )
        return cursor.lastrowid

    def update(self, currency: Currency) -> None:
        self._uow.conn.execute(
            "UPDATE currencies SET name = ?, is_active = ? WHERE id = ?",
            (currency.name, int(currency.is_active), currency.id)
        )

    def get_by_id(self, currency_id: int) -> Optional[Currency]:
        row = self._uow.conn.execute(
            "SELECT id, name, code, is_active FROM currencies WHERE id = ?", 
            (currency_id,)
        ).fetchone()
        
        if not row:
            return None
            
        return Currency(
            id=row['id'],
            name=row['name'],
            code=CurrencyCode(row['code']),
            is_active=bool(row['is_active'])
        )

    def get_by_code(self, code: CurrencyCode) -> Optional[Currency]:
        row = self._uow.conn.execute(
            "SELECT id, name, code, is_active FROM currencies WHERE code = ?", 
            (code.value,)
        ).fetchone()
        
        if not row:
            return None
            
        return Currency(
            id=row['id'],
            name=row['name'],
            code=CurrencyCode(row['code']),
            is_active=bool(row['is_active'])
        )