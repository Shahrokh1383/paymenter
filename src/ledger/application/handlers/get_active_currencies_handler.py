from typing import List
from src.ledger.application.queries.get_active_currencies_query import GetActiveCurrenciesQuery
from src.ledger.application.ports.currency_query_port import CurrencyQueryPort
from src.ledger.application.dto.currency_summary import CurrencySummaryDTO

class GetActiveCurrenciesHandler:
    def __init__(self, query_port: CurrencyQueryPort):
        self._query_port = query_port

    def handle(self, query: GetActiveCurrenciesQuery) -> List[CurrencySummaryDTO]:
        return self._query_port.get_active()