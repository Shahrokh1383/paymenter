from typing import Optional
from src.notifications.domain.ports.merchant_details_port import MerchantDetailsPort
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

class SqliteMerchantDetailsAdapter(MerchantDetailsPort):
    """Fetches merchant details for the Notifications context independently of the main UoW."""
    
    def get_merchant_name(self, merchant_id: int) -> Optional[str]:
        uow = SqliteUnitOfWork()
        with uow:
            row = uow.conn.execute("SELECT name FROM merchants WHERE id = ?", (merchant_id,)).fetchone()
            return row['name'] if row else None