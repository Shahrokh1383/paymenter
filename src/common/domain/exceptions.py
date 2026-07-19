class DomainException(Exception):
    """Base exception for all domain-level errors."""
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
    pass

class UserAlreadyExistsError(DomainException):
    pass

class CurrencyNotFoundError(DomainException):
    pass

class CurrencyAlreadyExistsError(DomainException):
    pass

class NonZeroBalanceCurrencyChangeError(DomainException):
    """Raised when attempting to change currency on an account with a non-zero balance."""
    pass

class InvalidTopupAmountError(DomainException):
    """Raised when a topup amount is less than or equal to zero."""
    pass