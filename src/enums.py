from enum import Enum


class AccountStatuses(Enum):
    ACTIVE = "Active"
    FROZEN = "Frozen"
    CLOSED = "Closed"


class Currencies(Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


class AccountTypes(Enum):
    BANK_ACCOUNT = "Bank account"
    SAVINGS_ACCOUNT = "Savings account"
    PREMIUM_ACCOUNT = "Premium account"
    INVESTMENT_ACCOUNT = "Investment account"

class TransactionTypes(Enum):
    DEPOSIT = "Deposit"
    WITHDRAW = "Withdraw"
    TRANSFER = "Transfer"

class TransactionStatuses(Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
