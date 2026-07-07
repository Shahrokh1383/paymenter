from typing import List
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.application.ports.currency_query_port import CurrencyQueryPort
from src.ledger.application.dto.currency_summary import CurrencySummaryDTO

class SqliteCurrencyQueryRepository(CurrencyQueryPort):
    """SQLite implementation for Currency Read Models."""
    
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_all(self) -> List[CurrencySummaryDTO]:
        rows = self._uow.conn.execute(
            "SELECT id, name, code, is_active FROM currencies"
        ).fetchall()
        
        return [
            CurrencySummaryDTO(
                id=row['id'],
                name=row['name'],
                code=CurrencyCode(row['code']),
                is_active=bool(row['is_active'])
            ) for row in rows
        ]

    def get_active(self) -> List[CurrencySummaryDTO]:
        rows = self._uow.conn.execute(
            "SELECT id, name, code, is_active FROM currencies WHERE is_active = 1"
        ).fetchall()
        
        return [
            CurrencySummaryDTO(
                id=row['id'],
                name=row['name'],
                code=CurrencyCode(row['code']),
                is_active=bool(row['is_active'])
            ) for row in rows
        ]