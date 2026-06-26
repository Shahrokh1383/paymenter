import secrets
from src.checkout.domain.ports.otp_generator import OtpGenerator
from src.checkout.domain.value_objects.otp_code import OtpCode

class SecureOtpGenerator(OtpGenerator):
    def generate(self) -> OtpCode:
        # secrets.choice is cryptographically stronger than random.choices
        code = ''.join(secrets.choice('0123456789') for _ in range(5))
        return OtpCode(code)