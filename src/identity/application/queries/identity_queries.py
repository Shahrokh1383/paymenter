from dataclasses import dataclass

@dataclass(frozen=True)
class GetAllUsersQuery:
    pass

@dataclass(frozen=True)
class SearchUsersQuery:
    query: str

@dataclass(frozen=True)
class GetAllMerchantsQuery:
    pass

@dataclass(frozen=True)
class GetAllCurrenciesQuery:
    pass