LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS currencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    name TEXT NOT NULL, 
    code TEXT NOT NULL UNIQUE, 
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER,  
    currency_id INTEGER NOT NULL, 
    account_number TEXT NOT NULL UNIQUE, 
    balance TEXT NOT NULL DEFAULT '0.00', 
    version INTEGER NOT NULL DEFAULT 0, 
    FOREIGN KEY (user_id) REFERENCES users(id), 
    FOREIGN KEY (currency_id) REFERENCES currencies(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    merchant_id INTEGER, 
    from_account_id INTEGER NOT NULL, 
    to_account_id INTEGER NOT NULL, 
    amount TEXT NOT NULL, 
    currency_id INTEGER NOT NULL, 
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