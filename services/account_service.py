from database.transaction import transaction
from repositories import account_repo, currency_repo
from utils.generators import generate_account_number, generate_card_number

class AccountBalanceError(Exception): pass
class InvalidAmountError(Exception): pass

def get_all():
    return account_repo.get_all()

def get_active_currencies():
    return currency_repo.get_active()

def update_currency(account_id, currency_id):
    with transaction() as conn:
        # Safety check: Prevent changing currency if balance is not 0
        cursor = conn.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
        account = cursor.fetchone()
        if account and account['balance'] > 0:
            raise AccountBalanceError("Cannot change currency on an account with a balance greater than 0. Please withdraw or transfer funds first.")
        
        account_repo.update_currency(conn, account_id, currency_id)

def add(user_id, currency_id):
    with transaction() as conn:
        acc_num = generate_account_number(lambda x: account_repo.exists_by_account_number(conn, x))
        card_num = generate_card_number(lambda x: account_repo.exists_by_card_number(conn, x))
        return account_repo.insert(conn, user_id, currency_id, acc_num, card_num)

def topup(account_id, amount):
    # Validation for positive amounts
    if amount <= 0:
        raise InvalidAmountError("Topup amount must be greater than zero.")
    
    with transaction() as conn:
        account_repo.topup(conn, account_id, amount)