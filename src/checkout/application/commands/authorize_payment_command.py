from dataclasses import dataclass

@dataclass(frozen=True)
class AuthorizePaymentCommand:
    session_token: str
    card_number: str
    otp_input: str