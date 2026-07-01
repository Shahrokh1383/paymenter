from dataclasses import dataclass
from decimal import Decimal
from src.common.domain.exceptions import CurrencyMismatchError
from src.common.domain.value_objects.currency_code import CurrencyCode

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: CurrencyCode

    def __post_init__(self):
        # Ensure precision is maintained
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        object.__setattr__(self, 'amount', self.amount.quantize(Decimal('0.01')))
        
        if isinstance(self.currency, str):
            object.__setattr__(self, 'currency', CurrencyCode(self.currency))
        elif not isinstance(self.currency, CurrencyCode):
            raise ValueError("Currency must be a CurrencyCode instance or a valid string.")

    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot add {self.currency.value} to {other.currency.value}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot subtract {other.currency.value} from {self.currency.value}")
        return Money(self.amount - other.amount, self.currency)

    def is_negative(self) -> bool:
        return self.amount < 0