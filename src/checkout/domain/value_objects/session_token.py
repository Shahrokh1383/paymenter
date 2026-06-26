from dataclasses import dataclass

@dataclass(frozen=True)
class SessionToken:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not self.value.startswith("gw_"):
            raise ValueError("SessionToken must be a valid gateway token starting with 'gw_'.")