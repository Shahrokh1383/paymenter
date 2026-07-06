from dataclasses import dataclass
from src.identity.domain.value_objects.api_key import ApiKey

@dataclass
class Merchant:
    id: int
    name: str
    api_key: ApiKey
    is_active: bool
    
    def toggle(self) -> None: 
        self.is_active = not self.is_active