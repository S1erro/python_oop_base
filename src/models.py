from enum import Enum
from pydantic import BaseModel, EmailStr, Field
import uuid
from .exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InsufficientFundsError,
    InvalidOperationError,
)
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal


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


class InvestmentPortfolio(BaseModel):
    balance: int  # Баланс инвестиционного портфеля
    yearly_rate: Decimal  # Годовой процент (%)


class Stocks(BaseModel):
    company_name: str  # Название компании
    stocks_count: int  # Количество


class Bonds(BaseModel):
    issuer_name: str  # Кто выпустил бонд (какой банк, государство или компания)
    bonds_count: int  # Количество
    coupon_rate: Decimal  # Месячная прибыль с одного купона


class AbstractAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[-12:])
    current_balance: int = 0
    acc_status: AccountStatuses = AccountStatuses.ACTIVE
    name: str
    surname: str
    email: EmailStr
    phone_number: str

    def deposit(
        self, amount: int
    ):  # amount == 10000 ==> 100.00 USD/RUB/EUR/KZT/CNY (количество денег в "копейках")
        pass

    def withdraw(
        self, amount: int
    ):  # amount == 10000 ==> 100.00 USD/RUB/EUR/KZT/CNY (количество денег в "копейках")
        pass

    def get_account_info(self):
        pass


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

    def deposit(self, amount: int):
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
        interest = interest = int( # Месячная выгода
            (Decimal(self.current_balance) * self.monthly_rate).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        self.current_balance += interest


class PremiumAccount(BankAccount):
    account_type: Literal[AccountTypes.PREMIUM_ACCOUNT] = AccountTypes.PREMIUM_ACCOUNT
    available_overdraft: int
    commission: Decimal  # commission < 1 (0.07 - 7%)

    def __str__(self):
        return f"""
Account type: {self.account_type.value}
Client: {self.name} {self.surname}
Phone: {"*" * (len(self.phone_number) - 4) + self.phone_number[-4:]}
Account status: {self.acc_status.value}
Balance: {self.current_balance / 100} {self.currency.value}
"""

    def withdraw(self, amount: int) -> None:
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
        )  # Банковский метод округления, чтобы не терять копейку
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
    account_type: Literal[AccountTypes.INVESTMENT_ACCOUNT] = AccountTypes.INVESTMENT_ACCOUNT
    investment_portfolios: list[InvestmentPortfolio] = Field(
        default_factory=list
    )  # Портфели
    stocks: list[Stocks] = Field(default_factory=list)  # Акции
    bonds: list[Bonds] = Field(default_factory=list)  # Бонды

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

    # Не вижу смысла переопределять на данном этапе этот метод
    # Т.к. вывод денег идентичен родительскому
    # def withdraw(self, amount):
    #     return super().withdraw(amount)

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

    def project_yearly_growth(self):  # Количество денег за год от бондов и портфелей
        yearly_growth_amount: Decimal = Decimal("0")

        for portfolio in self.investment_portfolios:
            yearly_growth_amount += Decimal(portfolio.balance) * portfolio.yearly_rate

        for bond in self.bonds:
            yearly_growth_amount += Decimal(bond.bonds_count) * bond.coupon_rate

        return int(yearly_growth_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


if __name__ == "__main__":

    print("\n--- BANK ACCOUNT TEST ---")
    bank = BankAccount(
        name="John",
        surname="Doe",
        email="john@example.com",
        phone_number="1234567890",
        currency=Currencies.USD,
    )

    bank.deposit(10_000)
    bank.withdraw(3_000)
    print(bank)


    print("\n--- SAVINGS ACCOUNT TEST ---")
    savings = SavingsAccount(
        name="Anna",
        surname="Smith",
        email="anna@example.com",
        phone_number="1111222233",
        currency=Currencies.EUR,
        min_balance=5_000,
        monthly_rate=Decimal("0.10"),
    )

    savings.deposit(20_000)
    savings.apply_monthly_interest()
    print(savings)

    try:
        savings.withdraw(18_000)
    except Exception as e:
        print("Savings withdraw error:", e)


    print("\n--- PREMIUM ACCOUNT TEST ---")
    premium = PremiumAccount(
        name="Mike",
        surname="Brown",
        email="mike@example.com",
        phone_number="9999888877",
        currency=Currencies.USD,
        available_overdraft=5_000,
        commission=Decimal("0.10"),
    )

    premium.deposit(10_000)
    premium.withdraw(10_000)  # с комиссией
    print(premium)
    print("Remaining overdraft:", premium.available_overdraft)


    print("\n--- INVESTMENT ACCOUNT TEST ---")
    invest = InvestmentAccount(
        name="Investor",
        surname="Pro",
        email="investor@example.com",
        phone_number="5555444433",
        currency=Currencies.USD,
    )

    invest.investment_portfolios.append(
        InvestmentPortfolio(balance=10_000, yearly_rate=Decimal("0.10"))
    )

    invest.bonds.append(
        Bonds(issuer_name="Bank", bonds_count=10, coupon_rate=Decimal("100"))
    )

    growth = invest.project_yearly_growth()
    print("Projected yearly growth:", growth)
    print(invest)


    print("\n--- STATUS TEST ---")
    frozen = BankAccount(
        name="Frozen",
        surname="User",
        email="frozen@example.com",
        phone_number="0000000000",
        currency=Currencies.USD,
        acc_status=AccountStatuses.FROZEN,
    )

    try:
        frozen.deposit(1_000)
    except Exception as e:
        print("Frozen account error:", e)