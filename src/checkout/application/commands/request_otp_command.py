from dataclasses import dataclass

@dataclass(frozen=True)
class RequestOtpCommand:
    session_token: str
    card_number: str