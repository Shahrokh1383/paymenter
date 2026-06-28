from typing import Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.checkout.domain.ports.account_lookup_port import AccountLookupPort

class IdentityAccountLookupAdapter(AccountLookupPort):
    """Read-model adapter to resolve Account IDs via Identity context mappings."""
    
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def get_account_id_by_card_number(self, card_number: str) -> Optional[int]:
        row = self._uow.conn.execute(
            "SELECT account_id FROM user_cards WHERE card_number = ?", (card_number,)
        ).fetchone()
        return row['account_id'] if row else None

    def get_settlement_account_id(self, merchant_id: int, currency_code: str) -> Optional[int]:
        # This query remains valid as it resolves merchant configuration
        row = self._uow.conn.execute("""
            SELECT m.settlement_account_id 
            FROM merchants m
            JOIN accounts a ON m.settlement_account_id = a.id
            JOIN currencies c ON a.currency_id = c.id
            WHERE m.id = ? AND c.code = ? AND m.is_active = 1
        """, (merchant_id, currency_code)).fetchone()
        
        return row['settlement_account_id'] if row else None