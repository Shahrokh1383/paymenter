from typing import List, Any
from src.identity.domain.repositories import UserRepository, MerchantRepository
from src.identity.application.queries.identity_queries import (
    GetAllUsersQuery, SearchUsersQuery, GetAllMerchantsQuery
)
from src.identity.application.dto.user_summary import UserSummaryDTO
from src.identity.application.dto.merchant_summary import MerchantSummaryDTO

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
    def __init__(self, merchant_repo: MerchantRepository): 
        self._repo = merchant_repo
    def handle(self, query: GetAllMerchantsQuery) -> List[MerchantSummaryDTO]:
        return self._repo.get_all_summaries()