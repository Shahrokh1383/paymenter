import re
from dataclasses import dataclass

@dataclass(frozen=True)
class EmailAddress:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise TypeError("Email must be a string.")
        # Basic RFC-compliant email regex validation
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", self.value):
            raise ValueError(f"Invalid email address format: {self.value}")