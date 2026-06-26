from abc import ABC, abstractmethod
from src.checkout.domain.entities.payment_session import PaymentSession
from src.checkout.domain.value_objects.session_token import SessionToken

class PaymentSessionRepository(ABC):
    @abstractmethod
    def save(self, session: PaymentSession) -> int: 
        raise NotImplementedError
        
    @abstractmethod
    def get_by_token(self, token: SessionToken) -> PaymentSession: 
        raise NotImplementedError
        
    @abstractmethod
    def update(self, session: PaymentSession) -> None: 
        raise NotImplementedError