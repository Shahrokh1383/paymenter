from dataclasses import dataclass

@dataclass(frozen=True)
class CardNumber:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("Card number must be a string")
        
        stripped_value = self.value.strip()
        if not stripped_value.isdigit() or len(stripped_value) != 16:
            raise ValueError("Card number must be exactly 16 digits")
            
        if not self._passes_luhn_check(stripped_value):
            raise ValueError("Invalid card number (failed Luhn check)")
            
        object.__setattr__(self, 'value', stripped_value)

    def _passes_luhn_check(self, card_number: str) -> bool:
        total = 0
        reverse_digits = card_number[::-1]
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    def __str__(self):
        return f"****-****-****-{self.value[-4:]}"