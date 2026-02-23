from enum import Enum
from pydantic import BaseModel, EmailStr
import uuid


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
        if (self.acc_status.name == AccountStatuses.frozen.name) | (
            self.acc_status.name == AccountStatuses.closed.name
        ):
            print(f"The account is {self.acc_status.name}")
        elif amount < 0:
            print("Amount cannot be less then zero")
        else:
            self.current_balance += amount * 100
            print("Deposit successfully made")

    def withdraw(self, amount: float):
        if (self.acc_status.name == AccountStatuses.frozen.name) | (
            self.acc_status.name == AccountStatuses.closed.name
        ):
            print(f"The account is {self.acc_status.name}")
        elif amount < 0:
            print("Amount cannot be less then zero")
        else:
            self.current_balance += amount
            print("Deposit successfully made")

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


first_client = BankAccount(
    acc_status=AccountStatuses.active,
    currency=Currencies.USD,
    name="name",
    surname="surname",
    email="some@email.com",
    phone_number="8955124896",
)
first_client.deposit(1)
first_client.get_account_info()
