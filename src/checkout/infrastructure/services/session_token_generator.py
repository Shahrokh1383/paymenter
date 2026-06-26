import secrets
from typing import Callable
from src.checkout.domain.ports.session_token_generator import SessionTokenGenerator
from src.checkout.domain.value_objects.session_token import SessionToken

class SecureSessionTokenGenerator(SessionTokenGenerator):
    def generate(self, check_exists_func: Callable[[str], bool]) -> SessionToken:
        while True:
            raw_token = f"gw_{secrets.token_urlsafe(24)}"
            if not check_exists_func(raw_token):
                return SessionToken(raw_token)