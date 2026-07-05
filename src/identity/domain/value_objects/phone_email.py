import re
from dataclasses import dataclass

@dataclass(frozen=True)
class PhoneEmail:
    value: str

    PHONE_REGEX = re.compile(r"^\+?[1-9]\d{1,14}$")
    EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise TypeError("PhoneEmail must be a string.")
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("PhoneEmail cannot be empty.")
        # Determine if it's a phone number or email
        if '@' in stripped:
            if not self.EMAIL_REGEX.match(stripped):
                raise ValueError(f"Invalid email format: {stripped}")
            # Normalize email to lowercase
            object.__setattr__(self, 'value', stripped.lower())
        else:
            if not self.PHONE_REGEX.match(stripped):
                raise ValueError(f"Invalid phone number (E.164): {stripped}")
            object.__setattr__(self, 'value', stripped)

    def __str__(self) -> str:
        return self.value