from abc import ABC, abstractmethod
from src.checkout.domain.value_objects.otp_code import OtpCode

class OtpGenerator(ABC):
    @abstractmethod
    def generate(self) -> OtpCode:
        raise NotImplementedError