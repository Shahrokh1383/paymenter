from database.transaction import transaction
from repositories import account_repo
from utils.generators import generate_account_number, generate_card_number

def add(user_id, currency_id):
    with transaction() as conn:
        acc_num = generate_account_number(lambda x: account_repo.exists_by_account_number(conn, x))
        card_num = generate_card_number(lambda x: account_repo.exists_by_card_number(conn, x))
        return account_repo.insert(conn, user_id, currency_id, acc_num, card_num)

def topup(account_id, amount):
    with transaction() as conn:
        account_repo.topup(conn, account_id, amount)