CHECKOUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS gateway_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    token TEXT NOT NULL UNIQUE, 
    merchant_id INTEGER NOT NULL, 
    amount TEXT NOT NULL, 
    currency_id TEXT NOT NULL, 
    user_email TEXT NOT NULL, 
    callback_url TEXT NOT NULL, 
    otp_code TEXT, 
    otp_locked_card TEXT,
    otp_expires_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'Initiated', 
    transaction_id TEXT, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (merchant_id) REFERENCES merchants(id), 
    FOREIGN KEY (currency_id) REFERENCES currencies(id), 
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);
"""