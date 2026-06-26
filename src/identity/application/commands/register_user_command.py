from dataclasses import dataclass

@dataclass(frozen=True)
class RegisterUserCommand:
    name: str
    phone_email: str