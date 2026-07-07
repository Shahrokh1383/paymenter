from typing import List
from src.ledger.application.queries.get_all_currencies_query import GetAllCurrenciesQuery
from src.ledger.application.ports.currency_query_port import CurrencyQueryPort
from src.ledger.application.dto.currency_summary import CurrencySummaryDTO

class GetAllCurrenciesHandler:
    def __init__(self, query_port: CurrencyQueryPort):
        self._query_port = query_port

    def handle(self, query: GetAllCurrenciesQuery) -> List[CurrencySummaryDTO]:
        return self._query_port.get_all()