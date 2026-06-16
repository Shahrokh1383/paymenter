from database.transaction import transaction

# --- Custom Exceptions ---
class InsufficientFundsError(Exception): pass
class AccountNotFoundError(Exception): pass
class CurrencyMismatchError(Exception): pass
class InvalidTransactionStateError(Exception): pass

def hold_funds(from_account_id: int, to_account_id: int, amount: float, merchant_id: int = None, user_email: str = None) -> int:
    """
    Deducts funds from the source account and creates a Pending transaction.
    Automatically detects currency from the source account.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        # Fetch accounts
        cursor.execute("SELECT id, balance, currency_id FROM accounts WHERE id = ?", (from_account_id,))
        from_acc = cursor.fetchone()
        cursor.execute("SELECT id, balance, currency_id FROM accounts WHERE id = ?", (to_account_id,))
        to_acc = cursor.fetchone()

        # Validations
        if not from_acc or not to_acc:
            raise AccountNotFoundError("One or both accounts do not exist.")

        # Auto-detect currency from the source account
        transaction_currency_id = from_acc['currency_id']

        # ENFORCE CURRENCY MATCH
        if to_acc['currency_id'] != transaction_currency_id:
            raise CurrencyMismatchError("Source and Destination accounts must have the same currency.")

        if from_acc['balance'] < amount:
            raise InsufficientFundsError("Insufficient balance in the source account.")

        # Deduct from sender
        new_from_balance = from_acc['balance'] - amount
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_from_balance, from_account_id))

        # Create Pending transaction using the auto-detected currency
        cursor.execute("""
            INSERT INTO transactions (merchant_id, from_account_id, to_account_id, amount, currency_id, status, user_email)
            VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        """, (merchant_id, from_account_id, to_account_id, amount, transaction_currency_id, user_email))

        return cursor.lastrowid


def complete_funds(transaction_id: int) -> dict:
    with transaction() as conn:
        cursor = conn.cursor()
        # FIX: Added 'merchant_id' to the SELECT query
        cursor.execute("""
            SELECT id, merchant_id, to_account_id, amount, status, user_email, currency_id 
            FROM transactions WHERE id = ?
        """, (transaction_id,))
        txn = cursor.fetchone()
        if not txn: raise InvalidTransactionStateError("Transaction not found.")
        if txn['status'] != 'Pending': raise InvalidTransactionStateError(f"Transaction cannot be completed. Current status: {txn['status']}")
        
        # Add funds to destination (Merchant)
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn['amount'], txn['to_account_id']))
        cursor.execute("UPDATE transactions SET status = 'Success' WHERE id = ?", (transaction_id,))
        
        # Fetch currency code for email
        cursor.execute("SELECT code FROM currencies WHERE id = ?", (txn['currency_id'],))
        currency = cursor.fetchone()
        
        txn_dict = dict(txn)
        txn_dict['currency_code'] = currency['code'] if currency else 'UNKNOWN'
        return txn_dict


def fail_and_refund(transaction_id: int) -> dict:
    with transaction() as conn:
        cursor = conn.cursor()
        # FIX: Added 'merchant_id' to the SELECT query
        cursor.execute("""
            SELECT id, merchant_id, from_account_id, to_account_id, amount, status, user_email, currency_id 
            FROM transactions WHERE id = ?
        """, (transaction_id,))
        txn = cursor.fetchone()
        if not txn: raise InvalidTransactionStateError("Transaction not found.")
        if txn['status'] not in ('Pending', 'Success'): raise InvalidTransactionStateError(f"Transaction cannot be refunded. Current status: {txn['status']}")
        
        # 1. Always refund the source account (User)
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn['amount'], txn['from_account_id']))
        
        # to maintain double-entry bookkeeping balance.
        if txn['status'] == 'Success':
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (txn['amount'], txn['to_account_id']))
        
        # 3. Update transaction status
        new_status = 'Failed' if txn['status'] == 'Pending' else 'Refunded'
        cursor.execute("UPDATE transactions SET status = ? WHERE id = ?", (new_status, transaction_id))
        
        # Fetch currency code for email
        cursor.execute("SELECT code FROM currencies WHERE id = ?", (txn['currency_id'],))
        currency = cursor.fetchone()
        
        txn_dict = dict(txn)
        txn_dict['status'] = new_status
        txn_dict['currency_code'] = currency['code'] if currency else 'UNKNOWN'
        return txn_dict