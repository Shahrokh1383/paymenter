from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.application.ports.currency_query_port import CurrencyQueryPort

class SqliteCurrencyResolver(CurrencyQueryPort):
    """SQLite implementation of the CurrencyQueryPort."""
    
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_currency_code_by_id(self, currency_id: int) -> str:
        row = self._uow.conn.execute(
            "SELECT code FROM currencies WHERE id = ?", 
            (currency_id,)
        ).fetchone()
        
        if not row:
            raise ValueError(f"Currency with ID {currency_id} not found.")
            
        return row['code']