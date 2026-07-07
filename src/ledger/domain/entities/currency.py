from dataclasses import dataclass
from src.common.domain.value_objects.currency_code import CurrencyCode

@dataclass
class Currency:
    id: int
    name: str
    code: CurrencyCode
    is_active: bool

    @classmethod
    def create(cls, id: int, name: str, code: CurrencyCode) -> 'Currency':
        return cls(id=id, name=name, code=code, is_active=True)

    def activate(self) -> None:
        if self.is_active:
            return
        self.is_active = True

    def deactivate(self) -> None:
        if not self.is_active:
            return
        self.is_active = False
        
    def toggle(self) -> None:
        if self.is_active:
            self.deactivate()
        else:
            self.activate()