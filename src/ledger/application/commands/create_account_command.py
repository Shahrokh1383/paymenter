from dataclasses import dataclass

@dataclass
class CreateAccountCommand:
    user_id: int
    currency_code: str