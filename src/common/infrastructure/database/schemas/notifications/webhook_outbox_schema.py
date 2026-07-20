WEBHOOK_OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS webhook_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMP,
    next_attempt_at TIMESTAMP,
    signature TEXT NOT NULL,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
CREATE INDEX IF NOT EXISTS idx_webhook_outbox_status ON webhook_outbox(status, next_attempt_at);
"""