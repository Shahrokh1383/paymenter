from typing import List
from datetime import datetime, timezone
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.webhook.application.dto.webhook_delivery_dto import WebhookDeliveryDTO
from src.webhook.domain.ports.webhook_delivery_query_port import WebhookDeliveryQueryPort
from src.webhook.domain.ports.webhook_delivery_processor_port import WebhookDeliveryProcessorPort

class SqliteWebhookDeliveryRepository(WebhookDeliveryQueryPort, WebhookDeliveryProcessorPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def _format_dt(self, dt: datetime) -> str:
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _map_row(self, row) -> WebhookDeliveryDTO:
        return WebhookDeliveryDTO(
            id=row['id'], merchant_id=row['merchant_id'], event_type=row['event_type'],
            payload=row['payload'], signature=row['signature'], status=row['status'],
            attempts=row['attempts'], last_attempt_at=row['last_attempt_at'],
            next_attempt_at=row['next_attempt_at'], created_at=row['created_at']
        )

    def get_all(self) -> List[WebhookDeliveryDTO]:
        cursor = self._uow.conn.execute("SELECT * FROM webhook_outbox ORDER BY created_at DESC")
        return [self._map_row(row) for row in cursor.fetchall()]

    def get_pending(self, limit: int = 50) -> List[WebhookDeliveryDTO]:
        now_str = self._format_dt(datetime.now(timezone.utc))
        cursor = self._uow.conn.execute(
            "SELECT * FROM webhook_outbox WHERE status = 'pending' AND (next_attempt_at IS NULL OR next_attempt_at <= ?) LIMIT ?",
            (now_str, limit)
        )
        return [self._map_row(row) for row in cursor.fetchall()]

    def mark_as_sent(self, delivery_id: int) -> None:
        now_str = self._format_dt(datetime.now(timezone.utc))
        self._uow.conn.execute(
            "UPDATE webhook_outbox SET status = 'sent', attempts = attempts + 1, last_attempt_at = ? WHERE id = ?",
            (now_str, delivery_id)
        )

    def mark_as_failed(self, delivery_id: int) -> None:
        now_str = self._format_dt(datetime.now(timezone.utc))
        self._uow.conn.execute(
            "UPDATE webhook_outbox SET status = 'failed', attempts = attempts + 1, last_attempt_at = ? WHERE id = ?",
            (now_str, delivery_id)
        )

    def record_retry(self, delivery_id: int, attempts: int, next_attempt_at: datetime) -> None:
        now_str = self._format_dt(datetime.now(timezone.utc))
        next_attempt_str = self._format_dt(next_attempt_at)
        self._uow.conn.execute(
            "UPDATE webhook_outbox SET attempts = ?, last_attempt_at = ?, next_attempt_at = ? WHERE id = ?",
            (attempts, now_str, next_attempt_str, delivery_id)
        )

    def mark_for_retry(self, delivery_id: int) -> None:
        now_str = self._format_dt(datetime.now(timezone.utc))
        self._uow.conn.execute(
            "UPDATE webhook_outbox SET status = 'pending', attempts = 0, next_attempt_at = ? WHERE id = ?",
            (now_str, delivery_id)
        )