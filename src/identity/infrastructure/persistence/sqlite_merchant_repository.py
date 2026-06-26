from typing import List, Any, Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.repositories import MerchantRepository

class SqliteMerchantRepository(MerchantRepository):
    def __init__(self, uow: UnitOfWork): self._uow = uow

    def add(self, merchant: Merchant) -> int:
        cursor = self._uow.conn.execute(
            "INSERT INTO merchants (name, api_key, settlement_account_id) VALUES (?, ?, ?)",
            (merchant.name, merchant.api_key.value, merchant.settlement_account_id)
        )
        return cursor.lastrowid

    def update(self, merchant: Merchant) -> None:
        self._uow.conn.execute("UPDATE merchants SET is_active = ? WHERE id = ?", (merchant.is_active, merchant.id))

    def toggle_status(self, merchant_id: int) -> None:
        self._uow.conn.execute("UPDATE merchants SET is_active = NOT is_active WHERE id = ?", (merchant_id,))

    def get_all_summaries(self) -> List[Any]:
        return self._uow.conn.execute("""
            SELECT m.*, a.balance as settlement_balance 
            FROM merchants m LEFT JOIN accounts a ON m.settlement_account_id = a.id
        """).fetchall()

    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]:
        row = self._uow.conn.execute("SELECT * FROM merchants WHERE api_key = ?", (api_key.value,)).fetchone()
        if not row: return None
        return Merchant(id=row['id'], name=row['name'], api_key=ApiKey(row['api_key']), is_active=bool(row['is_active']), settlement_account_id=row['settlement_account_id'])