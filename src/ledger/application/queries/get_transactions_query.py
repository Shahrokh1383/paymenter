from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class GetTransactionsQuery:
    status_filter: Optional[str] = None