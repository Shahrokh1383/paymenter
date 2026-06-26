from typing import List
from src.ledger.application.ports.account_query_port import AccountQueryPort
from src.ledger.application.dto.account_summary import AccountSummary
from src.ledger.application.queries.get_all_accounts_query import GetAllAccountsQuery

class GetAllAccountsHandler:
    def __init__(self, query_port: AccountQueryPort):
        self._query_port = query_port

    def handle(self, query: GetAllAccountsQuery) -> List[AccountSummary]:
        return self._query_port.get_all_summaries()