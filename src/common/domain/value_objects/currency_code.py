from dataclasses import dataclass

@dataclass(frozen=True)
class CurrencyCode:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValueError("Currency code must be a string.")
            
        # Normalize to eliminate whitespace and casing issues
        normalized = self.value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError(f"Currency code must be a valid 3-letter ISO code, got '{self.value}'.")
            
        object.__setattr__(self, 'value', normalized)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CurrencyCode):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value