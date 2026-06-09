from database.transaction import transaction
from repositories import merchant_repo, user_repo, account_repo
from utils.generators import generate_api_key, generate_account_number, generate_card_number

def get_all():
    return merchant_repo.get_all()

def add(name):
    with transaction() as conn:
        api_key = generate_api_key()
        
        # 1. Create a system user for the merchant's settlement account
        user_id = user_repo.insert(conn, f"Merchant: {name}", f"system_merchant_{name}@paymenter.com")
        
        # 2. Create the settlement account (Assuming Toman currency_id=1)
        acc_num = generate_account_number(lambda x: account_repo.exists_by_account_number(conn, x))
        card_num = generate_card_number(lambda x: account_repo.exists_by_card_number(conn, x))
        settlement_account_id = account_repo.insert(conn, user_id, 1, acc_num, card_num)
        
        # 3. Create the merchant and link the settlement account
        merchant_repo.insert(conn, name, api_key, settlement_account_id)

def toggle(merchant_id, is_active):
    with transaction() as conn:
        merchant_repo.toggle(conn, merchant_id, is_active)