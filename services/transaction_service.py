from repositories import transaction_repo

def get_transactions(status=None):
    return transaction_repo.get_all(status)