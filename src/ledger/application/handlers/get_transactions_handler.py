from typing import List
from src.ledger.application.ports.transaction_query_port import TransactionQueryPort
from src.ledger.application.dto.transaction_list_item import TransactionListItem
from src.ledger.application.queries.get_transactions_query import GetTransactionsQuery

class GetTransactionsHandler:
    def __init__(self, query_port: TransactionQueryPort):
        self._query_port = query_port

    def handle(self, query: GetTransactionsQuery) -> List[TransactionListItem]:
        return self._query_port.get_all_summaries(query.status_filter)