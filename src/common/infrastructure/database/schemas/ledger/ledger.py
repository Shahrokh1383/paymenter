LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS currencies (
    id TEXT PRIMARY KEY, 
    name TEXT NOT NULL, 
    code TEXT NOT NULL UNIQUE, 
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, 
    user_id INTEGER,  
    merchant_id INTEGER,
    currency_id TEXT NOT NULL, 
    account_number TEXT NOT NULL UNIQUE, 
    balance INTEGER NOT NULL DEFAULT 0, 
    pending_holds INTEGER NOT NULL DEFAULT 0,
    open_authorizations INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 0, 
    FOREIGN KEY (user_id) REFERENCES users(id), 
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (currency_id) REFERENCES currencies(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, 
    merchant_id INTEGER, 
    from_account_id TEXT NOT NULL, 
    to_account_id TEXT NOT NULL, 
    amount INTEGER NOT NULL, 
    currency_id TEXT NOT NULL, 
    status TEXT NOT NULL, 
    user_email TEXT, 
    version INTEGER NOT NULL DEFAULT 0, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (merchant_id) REFERENCES merchants(id), 
    FOREIGN KEY (from_account_id) REFERENCES accounts(id), 
    FOREIGN KEY (to_account_id) REFERENCES accounts(id), 
    FOREIGN KEY (currency_id) REFERENCES currencies(id)
);
"""