from dataclasses import dataclass

@dataclass
class Currency:
    id: int
    name: str
    code: str
    is_active: bool
    
    def toggle(self) -> None: self.is_active = not self.is_active