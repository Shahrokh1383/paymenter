from typing import List
from src.ledger.application.ports.escrow_account_query_port import EscrowAccountQueryPort
from src.ledger.application.dto.escrow_account_summary import EscrowAccountSummary
from src.ledger.application.queries.get_all_escrow_accounts_query import GetAllEscrowAccountsQuery

class GetAllEscrowAccountsHandler:
    def __init__(self, query_port: EscrowAccountQueryPort):
        self._query_port = query_port

    def handle(self, query: GetAllEscrowAccountsQuery) -> List[EscrowAccountSummary]:
        return self._query_port.get_all_escrow_summaries()