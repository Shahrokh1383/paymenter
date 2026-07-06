import re
from dataclasses import dataclass

@dataclass(frozen=True)
class ApiKey:
    value: str

    VALID_KEY_REGEX = re.compile(r'^pay_[A-Za-z0-9\-_]{43}$')

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise TypeError("ApiKey must be a string.")
        if not self.VALID_KEY_REGEX.match(self.value):
            raise ValueError(
                "ApiKey must start with 'pay_' and contain exactly 43 URL-safe characters."
            )