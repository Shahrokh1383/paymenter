def seed_data(conn):
    """Inserts default data into the database if it's empty."""
    cursor = conn.cursor()

    # Check if currencies table is empty
    cursor.execute("SELECT COUNT(*) FROM currencies")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO currencies (name, code, is_active) VALUES (?, ?, ?)",
            ('Toman', 'IRR', True)
        )
        print("Seed data inserted: Default 'Toman' currency added.")
        conn.commit()
    else:
        print("Seed data skipped: Database already contains currencies.")