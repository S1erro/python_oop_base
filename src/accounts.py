import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from .enums import AccountStatuses, AccountTypes, Currencies
from .exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)


class InvestmentPortfolio(BaseModel):
    balance: int
    yearly_rate: Decimal


class Stocks(BaseModel):
    company_name: str
    stocks_count: int


class Bonds(BaseModel):
    issuer_name: str
    bonds_count: int
    coupon_rate: Decimal


class AbstractAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[-12:])
    current_balance: int = 0
    acc_status: AccountStatuses = AccountStatuses.ACTIVE
    name: str
    surname: str
    email: EmailStr
    phone_number: str

    def deposit(self, amount: int):
        pass

    def withdraw(self, amount: int):
        pass

    def get_account_info(self):
        pass

    @staticmethod
    def ensure_operation_allowed_now() -> None:
        current_hour = datetime.now().hour
        if 0 <= current_hour < 5:
            raise InvalidOperationError(
                "Operations are not allowed from 00:00 to 05:00"
            )


class BankAccount(AbstractAccount):
    account_type: Literal[AccountTypes.BANK_ACCOUNT] = AccountTypes.BANK_ACCOUNT
    currency: Currencies

    def __str__(self):
        return f"""
Account type: {self.account_type.value} 
Client: {self.name} {self.surname}
Phone: {"*" * (len(self.phone_number) - 4) + self.phone_number[-4:]}
Account status: {self.acc_status.value}
Balance: {self.current_balance / 100} {self.currency.value}
"""

    def deposit(self, amount: int) -> None:
        self.ensure_operation_allowed_now()
        if self.acc_status == AccountStatuses.FROZEN:
            raise AccountFrozenError()
        elif self.acc_status == AccountStatuses.CLOSED:
            raise AccountClosedError()
        elif amount <= 0:
            raise InvalidOperationError()
        else:
            self.current_balance += amount
            print("Deposit successfully made")

    def withdraw(self, amount: int) -> None:
        self.ensure_operation_allowed_now()
        if self.acc_status == AccountStatuses.FROZEN:
            raise AccountFrozenError()
        elif self.acc_status == AccountStatuses.CLOSED:
            raise AccountClosedError()
        elif amount <= 0:
            raise InvalidOperationError()
        elif self.current_balance < amount:
            raise InsufficientFundsError()
        else:
            self.current_balance -= amount
            print("Withdraw successfully made")

    def get_account_info(self):
        return {
            "AccountType": self.account_type.value,
            "Id": self.id,
            "CurrentBalance": self.current_balance,
            "AccStatus": self.acc_status,
            "Name": self.name,
            "Surname": self.surname,
            "Email": self.email,
            "PhoneNumber": self.phone_number,
            "Currency": self.currency,
        }


class SavingsAccount(BankAccount):
    account_type: Literal[AccountTypes.SAVINGS_ACCOUNT] = AccountTypes.SAVINGS_ACCOUNT
    min_balance: int
    monthly_rate: Decimal

    def __str__(self):
        return f"""
Account type: {self.account_type.value} 
Client: {self.name} {self.surname}
Phone: {"*" * (len(self.phone_number) - 4) + self.phone_number[-4:]}
Account status: {self.acc_status.value}
Balance: {self.current_balance / 100} {self.currency.value}
Min balance: {self.min_balance / 100} {self.currency.value}
Monthly rate: {self.monthly_rate} %
"""

    def withdraw(self, amount: int) -> None:
        self.ensure_operation_allowed_now()
        if self.acc_status == AccountStatuses.FROZEN:
            raise AccountFrozenError()
        elif self.acc_status == AccountStatuses.CLOSED:
            raise AccountClosedError()
        elif amount <= 0:
            raise InvalidOperationError()
        elif (self.current_balance - self.min_balance) < amount:
            raise InsufficientFundsError()
        else:
            self.current_balance -= amount
            print("Withdraw successfully made")

    def get_account_info(self):
        return {
            "AccountType": self.account_type.value,
            "Id": self.id,
            "CurrentBalance": self.current_balance,
            "AccStatus": self.acc_status,
            "Name": self.name,
            "Surname": self.surname,
            "Email": self.email,
            "PhoneNumber": self.phone_number,
            "MinBalance": self.min_balance,
            "MonthlyRate": self.monthly_rate,
        }

    def apply_monthly_interest(self):
        interest = int(
            (Decimal(self.current_balance) * self.monthly_rate).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        self.current_balance += interest


class PremiumAccount(BankAccount):
    account_type: Literal[AccountTypes.PREMIUM_ACCOUNT] = AccountTypes.PREMIUM_ACCOUNT
    overdraft_limit: int
    available_overdraft: int
    commission: Decimal

    def __str__(self):
        return f"""
Account type: {self.account_type.value}
Client: {self.name} {self.surname}
Phone: {"*" * (len(self.phone_number) - 4) + self.phone_number[-4:]}
Account status: {self.acc_status.value}
Balance: {self.current_balance / 100} {self.currency.value}
"""

    def deposit(self, amount: int) -> None:
        self.ensure_operation_allowed_now()
        if self.acc_status == AccountStatuses.FROZEN:
            raise AccountFrozenError()
        elif self.acc_status == AccountStatuses.CLOSED:
            raise AccountClosedError()
        elif amount <= 0:
            raise InvalidOperationError()

        remaining_amount: int = amount
        overdraft_debt: int = self.overdraft_limit - self.available_overdraft

        if overdraft_debt != 0:
            if overdraft_debt >= remaining_amount:
                self.available_overdraft += remaining_amount
                remaining_amount = 0
            else:
                remaining_amount -= overdraft_debt
                self.available_overdraft = self.overdraft_limit

        if remaining_amount == 0:
            print("Overdraft succesfully repaid")
            return

        return super().deposit(remaining_amount)

    def withdraw(self, amount: int) -> None:
        self.ensure_operation_allowed_now()
        if self.acc_status == AccountStatuses.FROZEN:
            raise AccountFrozenError()

        if self.acc_status == AccountStatuses.CLOSED:
            raise AccountClosedError()

        if amount <= 0:
            raise InvalidOperationError()

        total_amount = int(
            (Decimal(amount) * (self.commission + Decimal("1"))).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        available_total = self.current_balance + self.available_overdraft

        if available_total < total_amount:
            raise InsufficientFundsError()

        if self.current_balance <= total_amount:
            remaining_amount = total_amount - self.current_balance
            self.current_balance = 0
            self.available_overdraft -= remaining_amount
        else:
            self.current_balance -= total_amount
        print("Withdraw successfully made")

    def get_account_info(self):
        return {
            "AccountType": self.account_type.value,
            "Id": self.id,
            "CurrentBalance": self.current_balance,
            "AccStatus": self.acc_status,
            "Name": self.name,
            "Surname": self.surname,
            "Email": self.email,
            "PhoneNumber": self.phone_number,
            "AvailableOverdraft": self.available_overdraft,
            "Commission": self.commission,
        }


class InvestmentAccount(BankAccount):
    account_type: Literal[AccountTypes.INVESTMENT_ACCOUNT] = (
        AccountTypes.INVESTMENT_ACCOUNT
    )
    investment_portfolios: list[InvestmentPortfolio] = Field(default_factory=list)
    stocks: list[Stocks] = Field(default_factory=list)
    bonds: list[Bonds] = Field(default_factory=list)

    def __str__(self):
        return f"""
Account type: {self.account_type.value}
Client: {self.name} {self.surname}
Phone: {"*" * (len(self.phone_number) - 4) + self.phone_number[-4:]}
Account status: {self.acc_status.value}
Balance: {self.current_balance / 100} {self.currency.value}
Investment portfolio count: {len(self.investment_portfolios)}
Companies stocks count: {len(self.stocks)}
Bonds count: {len(self.bonds)}
"""

    def get_account_info(self):
        return {
            "AccountType": self.account_type.value,
            "Id": self.id,
            "CurrentBalance": self.current_balance,
            "AccStatus": self.acc_status,
            "Name": self.name,
            "Surname": self.surname,
            "Email": self.email,
            "PhoneNumber": self.phone_number,
            "InvestmentPortfolios": self.investment_portfolios,
            "Stocks": self.stocks,
            "Bonds": self.bonds,
        }

    def project_yearly_growth(self) -> int:
        yearly_growth_amount: Decimal = Decimal("0")

        for portfolio in self.investment_portfolios:
            yearly_growth_amount += Decimal(portfolio.balance) * portfolio.yearly_rate

        for bond in self.bonds:
            yearly_growth_amount += Decimal(bond.bonds_count) * bond.coupon_rate * 12

        return int(yearly_growth_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


exchange_rate_to_rub: dict[Currencies, Decimal] = {
    Currencies.USD: Decimal("78.84"),
    Currencies.CNY: Decimal("41.14"),
    Currencies.EUR: Decimal("91.7"),
    Currencies.KZT: Decimal("21.3"),
    Currencies.RUB: Decimal("1"),
}
