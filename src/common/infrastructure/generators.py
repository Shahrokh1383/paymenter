import secrets
import random
import string
from typing import Callable

def generate_api_key() -> str: return f"pay_{secrets.token_urlsafe(32)}"
def generate_otp_code() -> str: return ''.join(random.choices(string.digits, k=5))

def generate_card_number(check_exists_func: Callable[[str], bool]) -> str:
    while True:
        # Generate the first 15 random digits
        digits = [str(random.randint(0, 9)) for _ in range(15)]
        
        # Calculate the 16th digit (Luhn check digit)
        test_digits = digits + ['0']
        reverse_digits = test_digits[::-1]
        total = 0
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
            
        check_digit = (10 - (total % 10)) % 10
        num = ''.join(digits) + str(check_digit)
        
        if not check_exists_func(num): 
            return num

def generate_account_number(check_exists_func: Callable[[str], bool]) -> str:
    while True:
        num = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        if not check_exists_func(num): return num

def generate_gateway_token(check_exists_func: Callable[[str], bool]) -> str:
    while True:
        token = f"gw_{secrets.token_urlsafe(24)}"
        if not check_exists_func(token): return token