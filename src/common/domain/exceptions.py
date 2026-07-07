class DomainException(Exception):
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