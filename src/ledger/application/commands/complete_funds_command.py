from dataclasses import dataclass

@dataclass(frozen=True)
class CompleteFundsCommand:
    transaction_id: str