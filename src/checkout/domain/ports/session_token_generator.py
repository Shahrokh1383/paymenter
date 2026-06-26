from abc import ABC, abstractmethod
from typing import Callable
from src.checkout.domain.value_objects.session_token import SessionToken

class SessionTokenGenerator(ABC):
    @abstractmethod
    def generate(self, check_exists_func: Callable[[str], bool]) -> SessionToken:
        raise NotImplementedError