import sqlite3
from typing import List, Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.repositories import MerchantRepository
from src.identity.application.dto.merchant_summary import MerchantSummaryDTO

class SqliteMerchantRepository(MerchantRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def _map_row_to_merchant(self, row: sqlite3.Row) -> Merchant:
        return Merchant(
            id=row['id'], name=row['name'],
            api_key=ApiKey(row['api_key']), is_active=bool(row['is_active'])
        )

    def add(self, merchant: Merchant) -> int:
        cursor = self._uow.conn.execute(
            "INSERT INTO merchants (name, api_key, is_active) VALUES (?, ?, ?)",
            (merchant.name, merchant.api_key.value, merchant.is_active)
        )
        return cursor.lastrowid

    def update(self, merchant: Merchant) -> None:
        self._uow.conn.execute(
            "UPDATE merchants SET is_active = ? WHERE id = ?",
            (merchant.is_active, merchant.id)
        )

    def get_by_id(self, merchant_id: int) -> Optional[Merchant]:
        cursor = self._uow.conn.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,))
        row = cursor.fetchone()
        return self._map_row_to_merchant(row) if row else None

    def get_all_summaries(self) -> List[MerchantSummaryDTO]:
        rows = self._uow.conn.execute("SELECT * FROM merchant_summaries").fetchall()
        return [
            MerchantSummaryDTO(
                id=row['id'], name=row['name'], api_key=row['api_key'], is_active=bool(row['is_active'])
            ) for row in rows
        ]

    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]:
        cursor = self._uow.conn.execute("SELECT * FROM merchants WHERE api_key = ?", (api_key.value,))
        row = cursor.fetchone()
        return self._map_row_to_merchant(row) if row else None