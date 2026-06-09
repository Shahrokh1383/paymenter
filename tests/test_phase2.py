import sys
import os

# Add the project root to the sys.path to ensure imports work correctly
# when running the test from the root directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import init_db
from database.transaction import transaction
from services.ledger import hold_funds, complete_funds, fail_and_refund, InsufficientFundsError
from utils.generators import generate_api_key, generate_card_number, generate_account_number

def setup_dummy_data():
    """Inserts a currency, two users, and two accounts for testing."""
    with transaction() as conn:
        cursor = conn.cursor()
        
        # 1. Currency (ID: 1 is already created by seed.py in init_db)
        # 2. Merchants
        cursor.execute("INSERT INTO merchants (name, api_key) VALUES (?, ?)", 
                       ('Test Merchant', generate_api_key()))
        
        # 3. Users
        cursor.execute("INSERT INTO users (name, phone_email) VALUES (?, ?)", ('Alice', 'alice@test.com'))
        cursor.execute("INSERT INTO users (name, phone_email) VALUES (?, ?)", ('Bob', 'bob@test.com'))
        
        # 4. Accounts
        # Helper function to check if card/account exists (Required by generators)
        def card_exists(card): 
            cursor.execute("SELECT id FROM accounts WHERE card_number = ?", (card,))
            return cursor.fetchone() is not None
            
        def acc_exists(acc): 
            cursor.execute("SELECT id FROM accounts WHERE account_number = ?", (acc,))
            return cursor.fetchone() is not None

        # Alice Account (ID: 1) - Balance: 1000.0
        cursor.execute("INSERT INTO accounts (user_id, currency_id, account_number, card_number, balance) VALUES (?, ?, ?, ?, ?)",
                       (1, 1, generate_account_number(acc_exists), generate_card_number(card_exists), 1000.0))
        
        # Bob Account (ID: 2) - Balance: 500.0
        cursor.execute("INSERT INTO accounts (user_id, currency_id, account_number, card_number, balance) VALUES (?, ?, ?, ?, ?)",
                       (2, 1, generate_account_number(acc_exists), generate_card_number(card_exists), 500.0))

def test_generators():
    print("\n--- Testing Generators ---")
    api_key = generate_api_key()
    print(f"Generated API Key: {api_key}")
    
    # Simulate that the number does NOT exist in the database
    def never_exists(x): return False
    
    card = generate_card_number(check_exists_func=never_exists)
    print(f"Generated Card Number: {card} (Length: {len(card)})")

    acc = generate_account_number(check_exists_func=never_exists)
    print(f"Generated Account Number: {acc} (Length: {len(acc)})")

def test_ledger():
    print("\n--- Testing Ledger Engine ---")
    with transaction() as conn:
        cursor = conn.cursor()

        # Test 1: hold_funds
        print("1. Holding 200.0 from Alice to Bob...")
        txn_id = hold_funds(from_account_id=1, to_account_id=2, amount=200.0, currency_id=1, merchant_id=1)
        print(f"   Transaction ID: {txn_id} created (Pending)")
        
        cursor.execute("SELECT balance FROM accounts WHERE id = 1")
        alice_bal = cursor.fetchone()['balance']
        print(f"   Alice Balance after hold: {alice_bal} (Expected: 800.0)")

        # Test 2: complete_funds
        print("2. Completing transaction...")
        complete_funds(txn_id)
        
        cursor.execute("SELECT balance FROM accounts WHERE id = 2")
        bob_bal = cursor.fetchone()['balance']
        print(f"   Bob Balance after complete: {bob_bal} (Expected: 700.0)")

        # Test 3: fail_and_refund
        print("3. Creating another transaction to fail/refund...")
        txn_id_2 = hold_funds(from_account_id=1, to_account_id=2, amount=100.0, currency_id=1, merchant_id=1)
        print(f"   Transaction ID: {txn_id_2} created (Pending)")
        
        fail_and_refund(txn_id_2)
        cursor.execute("SELECT balance FROM accounts WHERE id = 1")
        alice_bal_after_refund = cursor.fetchone()['balance']
        print(f"   Alice Balance after refund: {alice_bal_after_refund} (Expected: 700.0, because 100 was returned)")

        # Test 4: Insufficient Funds
        print("4. Testing Insufficient Funds error...")
        try:
            hold_funds(from_account_id=1, to_account_id=2, amount=99999.0, currency_id=1, merchant_id=1)
        except InsufficientFundsError as e:
            print(f"   Correctly caught error: {e}")

if __name__ == "__main__":
    # Clean up previous test database if it exists to ensure a fresh test
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'storage', 'paymenter.db'))
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed old database for a fresh test run.")

    print("Initializing Database...")
    init_db()
    print("Setting up dummy data...")
    setup_dummy_data()
    test_generators()
    test_ledger()
    print("\nPhase 2 Testing Complete! All systems operational.")