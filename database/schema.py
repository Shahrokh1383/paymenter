def create_tables(conn):
    """Creates the database tables if they do not exist."""
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_email TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            api_key TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            settlement_account_id INTEGER,
            FOREIGN KEY (settlement_account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            currency_id INTEGER NOT NULL,
            account_number TEXT NOT NULL UNIQUE,
            card_number TEXT NOT NULL UNIQUE,
            balance REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (currency_id) REFERENCES currencies(id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER,
            from_account_id INTEGER NOT NULL,
            to_account_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            user_email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (merchant_id) REFERENCES merchants(id),
            FOREIGN KEY (from_account_id) REFERENCES accounts(id),
            FOREIGN KEY (to_account_id) REFERENCES accounts(id),
            FOREIGN KEY (currency_id) REFERENCES currencies(id)
        );

        CREATE TABLE IF NOT EXISTS gateway_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            merchant_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency_id INTEGER NOT NULL,
            user_email TEXT NOT NULL,
            callback_url TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Initiated',
            transaction_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (merchant_id) REFERENCES merchants(id),
            FOREIGN KEY (currency_id) REFERENCES currencies(id),
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
        );
    """)
    
    # Migration for existing databases (Add user_email to transactions if it doesn't exist)
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN user_email TEXT")
        conn.commit()
    except Exception:
        pass # Column already exists

    conn.commit()