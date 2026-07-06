from src.common.infrastructure.database.schemas.identity.merchant_summaries_schema import MERCHANT_SUMMARIES_SCHEMA

IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    name TEXT NOT NULL, 
    phone_email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER NOT NULL, 
    account_id INTEGER NOT NULL, 
    card_number TEXT NOT NULL UNIQUE, 
    FOREIGN KEY (user_id) REFERENCES users(id), 
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS user_summaries (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone_email TEXT NOT NULL,
    account_id INTEGER,
    account_number TEXT,
    card_number TEXT,
    balance TEXT DEFAULT '0.00',
    currency_code TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""" + MERCHANT_SUMMARIES_SCHEMA