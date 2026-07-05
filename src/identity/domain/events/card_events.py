from dataclasses import dataclass

@dataclass(frozen=True)
class CardAssignedEvent:
    account_id: int
    user_id: int
    card_number: str