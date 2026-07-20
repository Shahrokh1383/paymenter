from abc import ABC, abstractmethod

class HttpClientPort(ABC):
    """Port for sending HTTP requests to external services."""
    @abstractmethod
    def post(self, url: str, headers: dict, body: str) -> int:
        """Returns HTTP status code."""
        raise NotImplementedError