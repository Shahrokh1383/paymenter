class DomainException(Exception):
    """Base exception for domain rule violations."""
    pass

class InsufficientFundsError(DomainException):
    pass

class CurrencyMismatchError(DomainException):
    pass

class InvalidTransactionStateError(DomainException):
    pass