import secrets
import random

def generate_api_key() -> str:
    """Generates a secure, unique API key for merchants."""
    return f"pay_{secrets.token_urlsafe(32)}"

def generate_card_number(check_exists_func) -> str:
    """Generates a unique 16-digit card number."""
    while True:
        # Generate a 16-digit string
        card_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        if not check_exists_func(card_number):
            return card_number

def generate_account_number(check_exists_func) -> str:
    """Generates a unique standard account number."""
    while True:
        # Generate a 10-digit string
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        if not check_exists_func(account_number):
            return account_number