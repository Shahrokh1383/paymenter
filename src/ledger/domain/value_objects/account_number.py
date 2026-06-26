from dataclasses import dataclass

@dataclass(frozen=True)
class AccountNumber:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("Account number must be a string")
            
        stripped_value = self.value.strip()
        if not stripped_value.isdigit() or len(stripped_value) != 10:
            raise ValueError("Account number must be exactly 10 digits")
            
        object.__setattr__(self, 'value', stripped_value)

    def __str__(self):
        return self.value