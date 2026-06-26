from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    phone_email: str