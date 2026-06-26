from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass(frozen=True)
class CallbackUrl:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise TypeError("Callback URL must be a string.")
        try:
            result = urlparse(self.value)
            if not all([result.scheme, result.netloc]):
                raise ValueError("Callback URL must be a valid absolute URL with scheme and netloc.")
        except Exception:
            raise ValueError(f"Invalid Callback URL format: {self.value}")