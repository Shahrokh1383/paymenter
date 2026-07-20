from dataclasses import dataclass

@dataclass(frozen=True)
class FailAndRefundCommand:
    transaction_id: str