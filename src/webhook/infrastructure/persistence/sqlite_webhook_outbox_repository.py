from src.common.domain.ports.unit_of_work import UnitOfWork
from src.webhook.domain.ports.webhook_outbox_port import WebhookOutboxPort

class SqliteWebhookOutboxRepository(WebhookOutboxPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def add(self, merchant_id: int, event_type: str, payload: str, signature: str) -> None:
        self._uow.conn.execute(
            """INSERT INTO webhook_outbox 
               (merchant_id, event_type, payload, status, attempts, signature) 
               VALUES (?, ?, ?, 'pending', 0, ?)""",
            (merchant_id, event_type, payload, signature)
        )