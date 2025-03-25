class VaultException(Exception):
    """Base exception for vault operations"""
    pass

class TokenException(VaultException):
    """Raised when there are token-related issues"""
    pass

class InternalError(VaultException):
    """Raised when there's an internal server error"""
    pass

class NotFoundError(VaultException):
    """Raised when a requested resource is not found"""
    pass