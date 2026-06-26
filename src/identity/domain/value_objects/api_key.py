from dataclasses import dataclass

@dataclass(frozen=True)
class ApiKey:
    value: str