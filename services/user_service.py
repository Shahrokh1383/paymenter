from database.transaction import transaction
from repositories import user_repo, account_repo
from utils.generators import generate_account_number, generate_card_number

def get_all():
    return user_repo.get_all()

def search(query):
    with transaction() as conn:
        return user_repo.search(conn, query)

def add(name, phone_email):
    with transaction() as conn:
        user_id = user_repo.insert(conn, name, phone_email)
        # Automatically create a default Toman (currency_id=1) account for the user
        acc_num = generate_account_number(lambda x: account_repo.exists_by_account_number(conn, x))
        card_num = generate_card_number(lambda x: account_repo.exists_by_card_number(conn, x))
        account_repo.insert(conn, user_id, 1, acc_num, card_num)