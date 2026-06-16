import secrets
import random
import string

def generate_api_key() -> str:
    """Generates a secure, unique API key for merchants."""
    return f"pay_{secrets.token_urlsafe(32)}"

def generate_card_number(check_exists_func) -> str:
    """Generates a unique 16-digit card number."""
    while True:
        card_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        if not check_exists_func(card_number):
            return card_number

def generate_account_number(check_exists_func) -> str:
    """Generates a unique standard account number."""
    while True:
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        if not check_exists_func(account_number):
            return account_number

def generate_gateway_token(check_exists_func) -> str:
    """Generates a secure, unique token for payment gateway sessions."""
    while True:
        token = f"gw_{secrets.token_urlsafe(24)}"
        if not check_exists_func(token):
            return token

def generate_otp_code() -> str:
    """Generates a secure 5-digit OTP code."""
    return ''.join(random.choices(string.digits, k=5))