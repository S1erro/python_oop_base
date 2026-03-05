import uuid
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

from pydantic import BaseModel, EmailStr, Field, field_validator

from .accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
    exchange_rate_to_rub,
)
from .audit import AuditLog, RiskAnalyzer
from .enums import AccountStatuses, AccountTypes
from .exceptions import ClientIdUsed, InappropriateAge

if TYPE_CHECKING:
    from .transactions import Transaction, TransactionProcessor, TransactionQueue


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
    audit_log: AuditLog = Field(default_factory=lambda: AuditLog(file_path="audit.log"))
    risk_analyzer: RiskAnalyzer = Field(default_factory=RiskAnalyzer)

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

    def build_account_to_client_map(self) -> dict[str, str]:
        account_to_client: dict[str, str] = {}
        for client_id, client in self.clients_dict.items():
            for account_id in client.account_ids:
                account_to_client[account_id] = client_id
        return account_to_client

    def assess_transaction_risk(self, transaction: "Transaction") -> tuple[bool, str]:
        from .enums import AuditLevels

        account_to_client = self.build_account_to_client_map()
        risk_level, reasons, client_id = self.risk_analyzer.analyze(
            transaction,
            account_to_client,
        )

        if risk_level.value in {"medium", "high"}:
            self.audit_log.log(
                level=AuditLevels.WARNING,
                event_type="suspicious_transaction",
                message=f"Suspicious transaction reasons={reasons}",
                transaction_id=transaction.id,
                client_id=client_id,
                risk_level=risk_level,
                metadata={
                    "sender": transaction.sender_acc_id,
                    "receiver": transaction.receiver_acc_id,
                    "amount": transaction.amount,
                },
            )

        if self.risk_analyzer.is_dangerous(risk_level):
            self.audit_log.log(
                level=AuditLevels.CRITICAL,
                event_type="blocked_transaction",
                message=f"Transaction blocked by risk engine reasons={reasons}",
                transaction_id=transaction.id,
                client_id=client_id,
                risk_level=risk_level,
                metadata={
                    "sender": transaction.sender_acc_id,
                    "receiver": transaction.receiver_acc_id,
                    "amount": transaction.amount,
                },
            )
            return False, f"Blocked by risk analyzer: {', '.join(reasons)}"

        return True, ""

    def process_transactions_with_risk(
        self,
        queue: "TransactionQueue",
        processor: "TransactionProcessor",
        wait_for_scheduled: bool = True,
    ) -> list["Transaction"]:
        from .enums import AuditLevels, TransactionStatuses

        processed_transactions: list["Transaction"] = []

        while True:
            transaction = queue.get_next_transaction()
            if transaction is None:
                if wait_for_scheduled and queue.has_waiting_transactions():
                    time.sleep(0.1)
                    continue
                break

            is_allowed, reason = self.assess_transaction_risk(transaction)
            if not is_allowed:
                transaction.transaction_status = TransactionStatuses.FAILED
                transaction.failure_reason = reason
                transaction.processed_at = datetime.now()
                processed_transactions.append(transaction)
                continue

            result = processor.process_transaction(transaction, self.accounts_dict)
            if result.transaction_status == TransactionStatuses.PENDING:
                queue.requeue_transaction(result.id)
                continue

            if result.transaction_status == TransactionStatuses.COMPLETED:
                self.audit_log.log(
                    level=AuditLevels.INFO,
                    event_type="transaction_completed",
                    message="Transaction completed",
                    transaction_id=result.id,
                    metadata={
                        "type": result.transaction_type.value,
                        "amount": result.amount,
                    },
                )

            if result.transaction_status == TransactionStatuses.FAILED:
                account_to_client = self.build_account_to_client_map()
                client_id = account_to_client.get(result.sender_acc_id or "")
                self.audit_log.log(
                    level=AuditLevels.ERROR,
                    event_type="transaction_error",
                    message=result.failure_reason or "Transaction processing failed",
                    transaction_id=result.id,
                    client_id=client_id,
                    metadata={
                        "type": result.transaction_type.value,
                        "amount": result.amount,
                    },
                )

            processed_transactions.append(result)

        for transaction in queue.all_transactions.values():
            if transaction.transaction_status == TransactionStatuses.CANCELLED:
                processed_transactions.append(transaction)

        return processed_transactions
