from database.transaction import transaction
from repositories import currency_repo

class CurrencyExistsError(Exception): pass

def get_all():
    return currency_repo.get_all()

def add(name, code):
    with transaction() as conn:
        if currency_repo.exists_by_code(conn, code):
            raise CurrencyExistsError("Currency code already exists.")
        currency_repo.insert(conn, name, code)

def toggle(currency_id, is_active):
    with transaction() as conn:
        currency_repo.toggle(conn, currency_id, is_active)