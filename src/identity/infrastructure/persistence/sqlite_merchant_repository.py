from typing import List, Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.repositories import MerchantRepository
from src.identity.application.dto.merchant_summary import MerchantSummaryDTO

class SqliteMerchantRepository(MerchantRepository):
    def __init__(self, uow: UnitOfWork): self._uow = uow

    def add(self, merchant: Merchant) -> int:
        cursor = self._uow.conn.execute(
            "INSERT INTO merchants (name, api_key, settlement_account_id) VALUES (?, ?, ?)",
            (merchant.name, merchant.api_key.value, merchant.settlement_account_id)
        )
        return cursor.lastrowid

    def update(self, merchant: Merchant) -> None:
        self._uow.conn.execute(
            "UPDATE merchants SET is_active = ? WHERE id = ?",
            (merchant.is_active, merchant.id)
        )

    def get_by_id(self, merchant_id: int) -> Optional[Merchant]:
        row = self._uow.conn.execute(
            "SELECT id, name, api_key, is_active, settlement_account_id FROM merchants WHERE id = ?",
            (merchant_id,)
        ).fetchone()
        if not row:
            return None
        return Merchant(
            id=row['id'],
            name=row['name'],
            api_key=ApiKey(row['api_key']),
            is_active=bool(row['is_active']),
            settlement_account_id=row['settlement_account_id']
        )

    def get_all_summaries(self) -> List[MerchantSummaryDTO]:
        rows = self._uow.conn.execute(
            "SELECT id, name, api_key, is_active, settlement_balance FROM merchant_summaries"
        ).fetchall()
        return [
            MerchantSummaryDTO(
                id=row['id'],
                name=row['name'],
                api_key=row['api_key'],
                is_active=bool(row['is_active']),
                settlement_balance=row['settlement_balance']
            )
            for row in rows
        ]

    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]:
        row = self._uow.conn.execute(
            "SELECT id, name, api_key, is_active, settlement_account_id FROM merchants WHERE api_key = ?",
            (api_key.value,)
        ).fetchone()
        if not row:
            return None
        return Merchant(
            id=row['id'],
            name=row['name'],
            api_key=ApiKey(row['api_key']),
            is_active=bool(row['is_active']),
            settlement_account_id=row['settlement_account_id']
        )