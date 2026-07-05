from typing import List, Any
from src.identity.domain.repositories import UserRepository, MerchantRepository, CurrencyRepository
from src.identity.application.queries.identity_queries import (
    GetAllUsersQuery, SearchUsersQuery, GetAllMerchantsQuery, GetAllCurrenciesQuery
)
from src.identity.application.dto.user_summary import UserSummaryDTO
class GetAllUsersHandler:
    def __init__(self, user_repo: UserRepository):
        self._repo = user_repo
    def handle(self, query: GetAllUsersQuery) -> List[UserSummaryDTO]:
        return self._repo.get_all_summaries()

class SearchUsersHandler:
    def __init__(self, user_repo: UserRepository):
        self._repo = user_repo
    def handle(self, query: SearchUsersQuery) -> List[UserSummaryDTO]:
        return self._repo.search_summaries(query.query)

class GetAllMerchantsHandler:
    def __init__(self, merchant_repo: MerchantRepository): self._repo = merchant_repo
    def handle(self, query: GetAllMerchantsQuery) -> List[Any]: return self._repo.get_all_summaries()

class GetAllCurrenciesHandler:
    def __init__(self, currency_repo: CurrencyRepository): self._repo = currency_repo
    def handle(self, query: GetAllCurrenciesQuery) -> List[Any]: return self._repo.get_all()