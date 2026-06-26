from dataclasses import dataclass
import secrets

@dataclass(frozen=True)
class OtpCode:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or len(self.value) != 5 or not self.value.isdigit():
            raise ValueError("OTP Code must be a 5-digit string.")

    def verify(self, input_code: str) -> bool:
        """Uses constant-time comparison to prevent timing attacks."""
        return secrets.compare_digest(self.value, input_code)