from dataclasses import dataclass

@dataclass(frozen=True)
class TopupAccountCommand:
    account_id: int
    amount: float