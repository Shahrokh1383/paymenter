class DomainException(Exception):
    """Base exception for domain rule violations."""
    pass

class InsufficientFundsError(DomainException):
    pass

class CurrencyMismatchError(DomainException):
    pass

class InvalidTransactionStateError(DomainException):
    pass

class AccountNotFoundError(DomainException):
    pass

class ConcurrencyException(DomainException):
    """Raised when an optimistic locking conflict occurs (Lost Update)."""
    pass