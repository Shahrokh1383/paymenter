from dataclasses import dataclass
from decimal import Decimal
from src.common.domain.exceptions import CurrencyMismatchError

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        # Ensure precision is maintained (e.g., 2 decimal places for standard currencies)
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        object.__setattr__(self, 'amount', self.amount.quantize(Decimal('0.01')))
        
        if not isinstance(self.currency, str) or len(self.currency) != 3:
            raise ValueError("Currency must be a valid 3-letter ISO code (e.g., 'USD').")

    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot add {self.currency} to {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot subtract {other.currency} from {self.currency}")
        return Money(self.amount - other.amount, self.currency)

    def is_negative(self) -> bool:
        return self.amount < 0