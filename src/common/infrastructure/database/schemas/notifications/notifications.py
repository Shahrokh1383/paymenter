from src.common.infrastructure.database.schemas.notifications.webhook_outbox_schema import WEBHOOK_OUTBOX_SCHEMA

NOTIFICATIONS_SCHEMA = """
-- Idempotency tracking for cross-context Domain Events
CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""" + WEBHOOK_OUTBOX_SCHEMA