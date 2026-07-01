from dataclasses import dataclass

@dataclass(frozen=True)
class CreateCurrencyCommand:
    name: str
    code: str