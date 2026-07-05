from dataclasses import dataclass
from src.identity.domain.value_objects.phone_email import PhoneEmail

@dataclass(frozen=True)
class UserRegisteredEvent:
    user_id: int
    name: str
    phone_email: PhoneEmail