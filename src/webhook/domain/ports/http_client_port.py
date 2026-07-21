from abc import ABC, abstractmethod

class HttpClientPort(ABC):
    @abstractmethod
    def post(self, url: str, headers: dict, body: str) -> int:
        raise NotImplementedError