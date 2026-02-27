from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator
import uuid
from .exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InsufficientFundsError,
    InvalidOperationError,
    InappropriateAge,
    ClientIdUsed,
)
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Union
from typing_extensions import TypeAlias
from datetime import datetime


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


class ClientContacts(BaseModel):
    email: EmailStr  # Почта
    phone: str  # Телефонный номер


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
        interest = interest = int(  # Месячная выгода
            (Decimal(self.current_balance) * self.monthly_rate).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        self.current_balance += interest


class PremiumAccount(BankAccount):
    account_type: Literal[AccountTypes.PREMIUM_ACCOUNT] = AccountTypes.PREMIUM_ACCOUNT
    overdraft_limit: int
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
    account_type: Literal[AccountTypes.INVESTMENT_ACCOUNT] = (
        AccountTypes.INVESTMENT_ACCOUNT
    )
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

    def project_yearly_growth(
        self,
    ) -> int:  # Количество денег за год от бондов и портфелей
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


class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[-12:])
    name: str  # Имя
    surname: str  # Фамилия
    middlename: str  # Отчество
    age: int  # Возраст
    account_ids: set[str] = Field(default_factory=set)
    contacts: ClientContacts
    is_locked: bool = False
    failed_login_attempts: int = 0
    has_suspicious_activity: bool = False

    @field_validator("age")
    @classmethod
    def validate_age(cls, age: int) -> int:
        if age < 18:
            raise InappropriateAge()
        return age


class Bank(BaseModel):
    MAX_LOGIN_ATTEMPTS: int = 3
    accounts_dict: dict[str, BankAccount] = Field(default_factory=dict)  # Список счетов
    clients_dict: dict[str, Client] = Field(default_factory=dict)  # Список клиентов

    def add_client(self, client: Client) -> None:
        if client.id in self.clients_dict:
            raise ClientIdUsed()
        self.clients_dict[client.id] = client

    def create_account(
        self, client_id: str, account_type: AccountTypes, **additional_acc_info
    ) -> BankAccount:
        if client_id not in self.clients_dict:
            raise KeyError("No such id in the bank")

        map_account_type: dict[AccountTypes, type[BankAccount]] = {
            AccountTypes.BANK_ACCOUNT: BankAccount,
            AccountTypes.INVESTMENT_ACCOUNT: InvestmentAccount,
            AccountTypes.PREMIUM_ACCOUNT: PremiumAccount,
            AccountTypes.SAVINGS_ACCOUNT: SavingsAccount,
        }

        client = self.clients_dict[client_id]

        account_class = map_account_type.get(account_type)
        if account_class is None:
            raise ValueError(f"Unsupported account type {account_type}")

        new_account = account_class(
            name=client.name,
            surname=client.surname,
            email=client.contacts.email,
            phone_number=client.contacts.phone,
            **additional_acc_info,
        )

        self.accounts_dict[new_account.id] = new_account
        client.account_ids.add(new_account.id)

        return new_account

    def open_account(self, client_id: str, account_id: str) -> None:
        if client_id not in self.clients_dict:
            raise KeyError("No such client id in the bank")

        if account_id not in self.clients_dict[client_id].account_ids:
            raise KeyError("The client doesn't have account with given")
        else:
            self.accounts_dict[account_id].acc_status = AccountStatuses.ACTIVE

    def close_account(self, client_id: str, account_id: str) -> None:
        if client_id not in self.clients_dict:
            raise KeyError("No such client id in the bank")

        if account_id not in self.clients_dict[client_id].account_ids:
            raise KeyError("The client doesn't have account with given")
        else:
            self.accounts_dict[account_id].acc_status = AccountStatuses.CLOSED

    def freeze_account(self, client_id: str, account_id: str) -> None:
        if client_id not in self.clients_dict:
            raise KeyError("No such client id in the bank")

        if account_id not in self.clients_dict[client_id].account_ids:
            raise KeyError("The client doesn't have account with given")
        else:
            self.accounts_dict[account_id].acc_status = AccountStatuses.FROZEN

    def unfreeze_account(self, client_id: str, account_id: str) -> None:
        if client_id not in self.clients_dict:
            raise KeyError("No such client id in the bank")

        if account_id not in self.clients_dict[client_id].account_ids:
            raise KeyError("The client doesn't have account with given")
        else:
            self.accounts_dict[account_id].acc_status = AccountStatuses.ACTIVE

    def authenticate_client(self, client_id: str, phone_number: str) -> bool:
        """
        Аутентификация клиента по client_id + phone_number.

        Логика блокировки:
        - если клиент заблокирован -> сразу False;
        - если данные верные -> сбрасываем счётчик неудачных попыток;
        - если данные неверные -> увеличиваем счётчик;
        - при 3 (MAX_LOGIN_ATTEMPTS) неудачных попытках блокируем клиента.
        """
        client = self.clients_dict.get(client_id)
        if client is None:
            return False

        if client.is_locked:
            return False

        if client.contacts.phone == phone_number:
            client.failed_login_attempts = 0
            client.has_suspicious_activity = False
            return True

        client.failed_login_attempts += 1
        # Простая пометка подозрительной активности:
        # любой неуспешный вход помечает клиента как "подозрительный".
        client.has_suspicious_activity = True
        if client.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
            client.is_locked = True

        return False

    def search_accounts(self, account_id: str) -> BankAccount:
        return self.accounts_dict[account_id]

    def get_clients_ranking(
        self,
    ) -> list[dict]:  # Рейтинг клиентов по количеству счетов
        client_ranking: list[dict] = []
        for client_id in self.clients_dict:
            acc_count = len(self.clients_dict[client_id].account_ids)
            client = f"{self.clients_dict[client_id].name} {self.clients_dict[client_id].surname}"
            client_ranking.append({"acc_count": acc_count, "client": client})

        client_ranking.sort(key=lambda client: client["acc_count"], reverse=True)

        return client_ranking

    def get_total_balance(self) -> int:
        total_balance: Decimal = Decimal("0")

        for account in self.accounts_dict.values():
            total_balance += (
                Decimal(account.current_balance) / Decimal("100")
            ) * exchange_rate_to_rub[account.currency]

        return int(
            (total_balance * Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )


if __name__ == "__main__":
    print()
    # --- Integration tests for main functionality ---
    # To allow running tests at any time (including 00:00-05:00),
    # temporarily disable operation time restriction for this demo block.
    AbstractAccount.ensure_operation_allowed_now = staticmethod(lambda: None)

    print("\n=== BANK INTEGRATION TESTS ===")
    bank = Bank()

    # 1) Create clients
    client_1 = Client(
        name="John",
        surname="Doe",
        middlename="A",
        age=30,
        contacts=ClientContacts(email="john@example.com", phone="1111222233"),
    )
    client_2 = Client(
        name="Anna",
        surname="Smith",
        middlename="B",
        age=27,
        contacts=ClientContacts(email="anna@example.com", phone="9999888877"),
    )

    bank.add_client(client_1)
    bank.add_client(client_2)
    print("[OK] Clients created")

    # 2) Open accounts
    acc_1 = bank.create_account(
        client_id=client_1.id,
        account_type=AccountTypes.BANK_ACCOUNT,
        currency=Currencies.USD,
    )
    acc_2 = bank.create_account(
        client_id=client_1.id,
        account_type=AccountTypes.SAVINGS_ACCOUNT,
        currency=Currencies.EUR,
        min_balance=5_000,
        monthly_rate=Decimal("0.01"),
    )
    acc_3 = bank.create_account(
        client_id=client_2.id,
        account_type=AccountTypes.PREMIUM_ACCOUNT,
        currency=Currencies.RUB,
        overdraft_limit=10_000,
        available_overdraft=10_000,
        commission=Decimal("0.05"),
    )
    print("[OK] Accounts opened")

    # 3) Account operations
    acc_1.deposit(20_000)
    acc_1.withdraw(5_000)
    acc_2.deposit(30_000)
    acc_3.deposit(15_000)
    print("[OK] Deposit/withdraw operations")

    # 4) Authentication attempts and lock after 3 failures
    assert bank.authenticate_client(client_1.id, "0000000000") is False
    assert bank.authenticate_client(client_1.id, "0000000000") is False
    assert bank.authenticate_client(client_1.id, "0000000000") is False
    assert bank.clients_dict[client_1.id].is_locked is True
    print("[OK] 3 failed auth attempts -> client locked")

    assert bank.authenticate_client(client_2.id, "9999888877") is True
    print("[OK] Successful auth")

    # 5) Freeze / unfreeze / close account
    bank.freeze_account(client_2.id, acc_3.id)
    assert bank.accounts_dict[acc_3.id].acc_status == AccountStatuses.FROZEN

    try:
        acc_3.deposit(1_000)
    except AccountFrozenError:
        print("[OK] Frozen account blocks operations")

    bank.unfreeze_account(client_2.id, acc_3.id)
    assert bank.accounts_dict[acc_3.id].acc_status == AccountStatuses.ACTIVE

    bank.close_account(client_2.id, acc_3.id)
    assert bank.accounts_dict[acc_3.id].acc_status == AccountStatuses.CLOSED
    print("[OK] Freeze/unfreeze/close flow")

    # 6) Rankings and totals
    ranking = bank.get_clients_ranking()
    total_balance = bank.get_total_balance()

    print("\n--- Ranking ---")
    for row in ranking:
        print(row)

    print(f"\nTotal balance in RUB kopecks: {total_balance}")
    print("\n=== ALL TESTS PASSED ===")