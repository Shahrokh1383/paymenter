from typing import Optional
from src.notifications.domain.ports.merchant_details_port import MerchantDetailsPort
from database.connection import get_db_connection
from repositories import merchant_repo # Temporary legacy import for ACL

class LegacyMerchantAdapter(MerchantDetailsPort):
    """Anti-Corruption Layer adapter to shield Notifications from legacy DB schema."""
    
    def get_merchant_name(self, merchant_id: int) -> Optional[str]:
        conn = get_db_connection()
        try:
            merchant = merchant_repo.get_by_id(conn, merchant_id)
            return merchant['name'] if merchant else None
        finally:
            conn.close()