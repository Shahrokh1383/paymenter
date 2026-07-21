from typing import Optional
from src.common.infrastructure.database import create_connection
from src.identity.application.dto.webhook_config_dto import WebhookConfigDTO
from src.webhook.domain.ports.merchant_webhook_config_port import MerchantWebhookConfigPort

class SqliteMerchantWebhookConfigAdapter(MerchantWebhookConfigPort):
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def get_config(self, merchant_id: int) -> Optional[WebhookConfigDTO]:
        conn = self._connection_factory()
        cursor = conn.execute(
            "SELECT webhook_url, webhook_secret, webhook_enabled FROM merchants WHERE id = ?", 
            (merchant_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row: return None
        return WebhookConfigDTO(
            webhook_url=row['webhook_url'],
            webhook_secret=row['webhook_secret'],
            webhook_enabled=bool(row['webhook_enabled']) if row['webhook_enabled'] else False
        )