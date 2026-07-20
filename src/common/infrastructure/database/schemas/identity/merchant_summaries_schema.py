MERCHANT_SUMMARIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS merchant_summaries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    webhook_url TEXT,
    webhook_enabled BOOLEAN NOT NULL DEFAULT 0
);
"""