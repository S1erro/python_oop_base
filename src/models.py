from enum import Enum
from pydantic import BaseModel, EmailStr
import uuid
from .exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InsufficientFundsError,
    InvalidOperationError,
)


class AccountStatuses(Enum):
    active = "Active"
    frozen = "Frozen"
    closed = "Closed"


class Currencies(Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


class AbstractAccount(BaseModel):
    id: str = str(uuid.uuid4())[-12:]
    current_balance: int = 0
    acc_status: AccountStatuses = AccountStatuses.active
    name: str
    surname: str
    email: EmailStr
    phone_number: str

    def deposit(self, amount: float):
        pass

    def withdraw(self, amount: float):
        pass

    def get_account_info(self):
        pass


class BankAccount(AbstractAccount):
    currency: Currencies

    def deposit(self, amount: float):  # TODO: move to utils.py
        if self.acc_status.name == AccountStatuses.frozen.name:
            raise AccountFrozenError()
        elif self.acc_status.name == AccountStatuses.closed.name:
            raise AccountClosedError()
        elif amount <= 0:
            raise InvalidOperationError()
        else:
            self.current_balance += int(amount * 100)
            print("Deposit successfully made")

    def withdraw(self, amount: float):
        if self.acc_status.name == AccountStatuses.frozen.name:
            raise AccountFrozenError()
        elif self.acc_status.name == AccountStatuses.closed.name:
            raise AccountClosedError()
        elif amount <= 0:
            raise InsufficientFundsError()
        else:
            self.current_balance -= int(amount * 100)
            print("Withdraw successfully made")

    def get_account_info(self):  # TODO: output only 4 last digits of phone number
        print(
            f"""
Account type: {self.currency.value} 
Client: {self.name} {self.surname}
Phone: {"*" * (len(self.phone_number) - 4) + self.phone_number[-4:]}
Account status: {self.acc_status.value}
Balance: {self.current_balance / 100} {self.currency.value}
"""
        )


active_acc = BankAccount(
    acc_status=AccountStatuses.active,
    currency=Currencies.USD,
    name="name",
    surname="surname",
    email="some@email.com",
    phone_number="8955124896",
)

frozen_acc = BankAccount(
    acc_status=AccountStatuses.frozen,
    currency=Currencies.USD,
    name="name",
    surname="surname",
    email="some@email.com",
    phone_number="8955124896",
)

active_acc.deposit(1000)

active_acc.withdraw(189)

frozen_acc.deposit(1)
