from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.ports.currency_command_port import CurrencyCommandPort

class SqliteCurrencyCommandRepository(CurrencyCommandPort):
    """SQLite implementation for writing currency data."""
    
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def add_currency(self, name: str, code: str) -> int:
        cursor = self._uow.conn.execute(
            "INSERT INTO currencies (name, code, is_active) VALUES (?, ?, 1)",
            (name, code)
        )
        return cursor.lastrowid