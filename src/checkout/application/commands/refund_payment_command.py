from dataclasses import dataclass

@dataclass(frozen=True)
class RefundPaymentCommand:
    transaction_id: int