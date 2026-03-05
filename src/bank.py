import uuid
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, EmailStr, Field, field_validator

from .accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
    exchange_rate_to_rub,
)
from .enums import AccountStatuses, AccountTypes
from .exceptions import ClientIdUsed, InappropriateAge


class ClientContacts(BaseModel):
    email: EmailStr
    phone: str


class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[-12:])
    name: str
    surname: str
    middlename: str
    age: int
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
    accounts_dict: dict[str, BankAccount] = Field(default_factory=dict)
    clients_dict: dict[str, Client] = Field(default_factory=dict)

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
        client.has_suspicious_activity = True
        if client.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
            client.is_locked = True

        return False

    def search_accounts(self, account_id: str) -> BankAccount:
        return self.accounts_dict[account_id]

    def get_clients_ranking(self) -> list[dict]:
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
