class AccountFrozenError(Exception):
    """Operation rejected - frozen account"""

    def __init__(self, message: str = "The account is frozen"):
        super().__init__(message)

class AccountClosedError(Exception):
    """Operation rejected - closed account"""

    def __init__(self, message: str = "The account is closed"):
        super().__init__(message)

class InvalidOperationError(Exception):
    """Invalid operation with the account"""

    def __init__(self, message: str = "Invalid operation"):
        super().__init__(message)

class InsufficientFundsError(Exception):
    """Insufficient funds to complete the withdraw"""

    def __init__(self, message: str = "Insufficient funds"):
        super().__init__(message)

class InappropriateAge(Exception):
    """Inappropriate age to create an account"""

    def __init__(self, message: str = "Inappropriate age"):
        super().__init__(message)

class ClientIdUsed(Exception):
    """Cannot add client: id used"""

    def __init__(self, message: str = "Client id already used"):
        super().__init__(message)