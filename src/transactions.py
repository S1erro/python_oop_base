import uuid
import time
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from pydantic import BaseModel, Field

from .accounts import AbstractAccount, BankAccount, PremiumAccount, exchange_rate_to_rub
from .enums import (
    AccountStatuses,
    AccountTypes,
    Currencies,
    TransactionStatuses,
    TransactionTypes,
)


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_type: TransactionTypes
    amount: int
    currency: Currencies
    commission: Decimal = Decimal("0")
    sender_acc_id: Optional[str] = None
    receiver_acc_id: Optional[str] = None
    transaction_status: TransactionStatuses = TransactionStatuses.PENDING
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    first_priority: bool = False
    scheduled_at: Optional[datetime] = None
    retry_count: int = 0


class TransactionQueue(BaseModel):
    fp_transactions_queue: deque[str] = Field(default_factory=deque)
    transactions_queue: deque[str] = Field(default_factory=deque)
    all_transactions: dict[str, Transaction] = Field(default_factory=dict)

    def add_transaction(self, transaction: Transaction) -> None:
        if transaction.id in self.all_transactions:
            raise ValueError("Transaction with this id already exists in queue")

        self._enqueue(transaction)
        self.all_transactions[transaction.id] = transaction

    def requeue_transaction(self, transaction_id: str) -> None:
        transaction = self.all_transactions.get(transaction_id)
        if transaction is None:
            raise KeyError("Transaction not found")

        self._enqueue(transaction)

    def _enqueue(self, transaction: Transaction) -> None:
        if transaction.first_priority:
            self.fp_transactions_queue.append(transaction.id)
        else:
            self.transactions_queue.append(transaction.id)

    def _pop_ready_from_queue(self, queue: deque[str]) -> Optional[Transaction]:
        now = datetime.now()
        queue_length = len(queue)

        for _ in range(queue_length):
            transaction_id = queue.popleft()
            transaction = self.all_transactions[transaction_id]

            if transaction.transaction_status == TransactionStatuses.CANCELLED:
                continue

            if (
                transaction.scheduled_at is not None
                and transaction.scheduled_at > now
            ):
                queue.append(transaction_id)
                continue

            return transaction

        return None

    def get_next_transaction(self) -> Optional[Transaction]:
        transaction = self._pop_ready_from_queue(self.fp_transactions_queue)
        if transaction is not None:
            return transaction

        return self._pop_ready_from_queue(self.transactions_queue)

    def cancel_transaction(self, transaction_id: str) -> None:
        transaction = self.all_transactions.get(transaction_id)
        if transaction is None:
            raise KeyError("Transaction not found")

        if transaction.transaction_status == TransactionStatuses.COMPLETED:
            raise ValueError("Completed transaction cannot be cancelled")

        transaction.transaction_status = TransactionStatuses.CANCELLED
        transaction.failure_reason = "Cancelled by user"
        transaction.processed_at = datetime.now()

    def has_waiting_transactions(self) -> bool:
        for transaction in self.all_transactions.values():
            if transaction.transaction_status == TransactionStatuses.PENDING:
                return True
        return False


class TransactionProcessor(BaseModel):
    external_transfer_commission: Decimal = Decimal("0.02")
    max_retries: int = 2
    error_log: list[str] = Field(default_factory=list)

    @staticmethod
    def _convert_amount(amount: int, from_currency: Currencies, to_currency: Currencies) -> int:
        if from_currency == to_currency:
            return amount

        amount_major = Decimal(amount) / Decimal("100")
        amount_in_rub = amount_major * exchange_rate_to_rub[from_currency]
        converted_major = amount_in_rub / exchange_rate_to_rub[to_currency]

        return int(
            (converted_major * Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    @staticmethod
    def _ensure_not_frozen(account: Optional[BankAccount]) -> None:
        if account is not None and account.acc_status == AccountStatuses.FROZEN:
            raise ValueError("Operation rejected: account is frozen")

    @staticmethod
    def _ensure_account_active(account: Optional[BankAccount]) -> None:
        if account is not None and account.acc_status != AccountStatuses.ACTIVE:
            raise ValueError("Operation rejected: account is not active")

    def _resolve_commission_rate(self, sender: BankAccount, receiver: BankAccount) -> Decimal:
        is_external = sender.id != receiver.id
        if not is_external:
            return Decimal("0")

        if isinstance(sender, PremiumAccount):
            return sender.commission

        return self.external_transfer_commission

    def _debit_amount(self, sender: BankAccount, amount: int) -> None:
        if isinstance(sender, PremiumAccount):
            available_total = sender.current_balance + sender.available_overdraft
            if available_total < amount:
                raise ValueError("Insufficient funds even with overdraft")

            if sender.current_balance >= amount:
                sender.current_balance -= amount
            else:
                remaining = amount - sender.current_balance
                sender.current_balance = 0
                sender.available_overdraft -= remaining
            return

        if sender.current_balance - amount < 0:
            raise ValueError("Transfers resulting in negative balance are prohibited")

        sender.current_balance -= amount

    def _credit_amount(self, receiver: BankAccount, amount: int) -> None:
        receiver.current_balance += amount

    def process_transaction(
        self,
        transaction: Transaction,
        accounts: dict[str, BankAccount],
    ) -> Transaction:
        transaction.transaction_status = TransactionStatuses.PROCESSING

        try:
            sender = (
                accounts[transaction.sender_acc_id]
                if transaction.sender_acc_id is not None
                else None
            )
            receiver = (
                accounts[transaction.receiver_acc_id]
                if transaction.receiver_acc_id is not None
                else None
            )

            self._ensure_not_frozen(sender)
            self._ensure_not_frozen(receiver)
            self._ensure_account_active(sender)
            self._ensure_account_active(receiver)

            if transaction.transaction_type == TransactionTypes.DEPOSIT:
                if receiver is None:
                    raise ValueError("Receiver account is required for deposit")

                amount_to_credit = self._convert_amount(
                    transaction.amount, transaction.currency, receiver.currency
                )
                self._credit_amount(receiver, amount_to_credit)

            elif transaction.transaction_type == TransactionTypes.WITHDRAW:
                if sender is None:
                    raise ValueError("Sender account is required for withdraw")

                amount_to_debit = self._convert_amount(
                    transaction.amount, transaction.currency, sender.currency
                )
                self._debit_amount(sender, amount_to_debit)

            elif transaction.transaction_type == TransactionTypes.TRANSFER:
                if sender is None or receiver is None:
                    raise ValueError("Both sender and receiver are required for transfer")

                amount_to_debit = self._convert_amount(
                    transaction.amount, transaction.currency, sender.currency
                )
                commission_rate = self._resolve_commission_rate(sender, receiver)
                commission_value = int(
                    (Decimal(amount_to_debit) * commission_rate).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )
                total_debit = amount_to_debit + commission_value
                transaction.commission = Decimal(commission_value)

                self._debit_amount(sender, total_debit)

                amount_to_credit = self._convert_amount(
                    transaction.amount, transaction.currency, receiver.currency
                )
                self._credit_amount(receiver, amount_to_credit)

            transaction.transaction_status = TransactionStatuses.COMPLETED
            transaction.failure_reason = None
            transaction.processed_at = datetime.now()
            return transaction

        except Exception as error:
            transaction.retry_count += 1
            transaction.failure_reason = str(error)

            if transaction.retry_count <= self.max_retries:
                transaction.transaction_status = TransactionStatuses.PENDING
            else:
                transaction.transaction_status = TransactionStatuses.FAILED
                transaction.processed_at = datetime.now()

            self.error_log.append(
                f"[{datetime.now().isoformat(timespec='seconds')}] "
                f"transaction={transaction.id} error={error}"
            )
            return transaction

    def process_queue(
        self,
        queue: TransactionQueue,
        accounts: dict[str, BankAccount],
        wait_for_scheduled: bool = True,
    ) -> list[Transaction]:
        processed_transactions: list[Transaction] = []

        while True:
            transaction = queue.get_next_transaction()
            if transaction is None:
                if wait_for_scheduled and queue.has_waiting_transactions():
                    time.sleep(0.1)
                    continue
                break

            result = self.process_transaction(transaction, accounts)
            if result.transaction_status == TransactionStatuses.PENDING:
                queue.requeue_transaction(result.id)
            else:
                processed_transactions.append(result)

        for transaction in queue.all_transactions.values():
            if transaction.transaction_status == TransactionStatuses.CANCELLED:
                processed_transactions.append(transaction)

        return processed_transactions


def run_transactions_demo() -> None:
    from .bank import Bank, Client, ClientContacts

    AbstractAccount.ensure_operation_allowed_now = staticmethod(lambda: None)

    bank = Bank()
    client_1 = Client(
        name="Ivan",
        surname="Petrov",
        middlename="A",
        age=29,
        contacts=ClientContacts(email="ivan@example.com", phone="7000000001"),
    )
    client_2 = Client(
        name="Mila",
        surname="Sidorova",
        middlename="B",
        age=33,
        contacts=ClientContacts(email="mila@example.com", phone="7000000002"),
    )

    bank.add_client(client_1)
    bank.add_client(client_2)

    acc_1 = bank.create_account(
        client_id=client_1.id,
        account_type=AccountTypes.BANK_ACCOUNT,
        currency=Currencies.RUB,
    )
    acc_2 = bank.create_account(
        client_id=client_1.id,
        account_type=AccountTypes.SAVINGS_ACCOUNT,
        currency=Currencies.USD,
        min_balance=0,
        monthly_rate=Decimal("0.01"),
    )
    acc_3 = bank.create_account(
        client_id=client_2.id,
        account_type=AccountTypes.PREMIUM_ACCOUNT,
        currency=Currencies.EUR,
        overdraft_limit=40_000,
        available_overdraft=40_000,
        commission=Decimal("0.01"),
    )
    acc_4 = bank.create_account(
        client_id=client_2.id,
        account_type=AccountTypes.BANK_ACCOUNT,
        currency=Currencies.RUB,
    )

    acc_1.current_balance = 200_000
    acc_2.current_balance = 100_000
    acc_3.current_balance = 50_000
    acc_4.current_balance = 0
    acc_2.acc_status = AccountStatuses.FROZEN

    queue = TransactionQueue()
    processor = TransactionProcessor(external_transfer_commission=Decimal("0.03"))

    transactions = [
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=10_000,
            currency=Currencies.RUB,
            sender_acc_id=acc_1.id,
            receiver_acc_id=acc_4.id,
            first_priority=True,
        ),
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=8_000,
            currency=Currencies.EUR,
            sender_acc_id=acc_3.id,
            receiver_acc_id=acc_1.id,
            first_priority=True,
        ),
        Transaction(
            transaction_type=TransactionTypes.DEPOSIT,
            amount=5_000,
            currency=Currencies.USD,
            receiver_acc_id=acc_4.id,
        ),
        Transaction(
            transaction_type=TransactionTypes.WITHDRAW,
            amount=3_000,
            currency=Currencies.RUB,
            sender_acc_id=acc_1.id,
        ),
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=1_000,
            currency=Currencies.USD,
            sender_acc_id=acc_2.id,
            receiver_acc_id=acc_4.id,
        ),
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=900_000,
            currency=Currencies.RUB,
            sender_acc_id=acc_1.id,
            receiver_acc_id=acc_4.id,
        ),
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=2_000,
            currency=Currencies.RUB,
            sender_acc_id=acc_4.id,
            receiver_acc_id=acc_1.id,
            scheduled_at=datetime.now() + timedelta(seconds=1),
        ),
        Transaction(
            transaction_type=TransactionTypes.DEPOSIT,
            amount=12_000,
            currency=Currencies.EUR,
            receiver_acc_id=acc_1.id,
            first_priority=True,
        ),
        Transaction(
            transaction_type=TransactionTypes.WITHDRAW,
            amount=700,
            currency=Currencies.EUR,
            sender_acc_id=acc_3.id,
        ),
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=2_500,
            currency=Currencies.RUB,
            sender_acc_id=acc_1.id,
            receiver_acc_id=acc_4.id,
        ),
        Transaction(
            transaction_type=TransactionTypes.TRANSFER,
            amount=350_000,
            currency=Currencies.RUB,
            sender_acc_id=acc_1.id,
            receiver_acc_id=acc_3.id,
            created_at=datetime.now().replace(hour=1, minute=30, second=0, microsecond=0),
        ),
    ]

    for tx in transactions:
        queue.add_transaction(tx)

    queue.cancel_transaction(transactions[-2].id)

    processed = bank.process_transactions_with_risk(queue, processor)

    print("=== PROCESSING RESULT ===")
    for tx in processed:
        print(
            tx.id,
            tx.transaction_type.value,
            tx.transaction_status.value,
            f"retry={tx.retry_count}",
            f"reason={tx.failure_reason}",
            f"commission_minor={tx.commission}",
        )

    print("\n=== ACCOUNT BALANCES (minor units) ===")
    for account in [acc_1, acc_2, acc_3, acc_4]:
        overdraft_part = (
            f", available_overdraft={account.available_overdraft}"
            if isinstance(account, PremiumAccount)
            else ""
        )
        print(
            f"acc={account.id} currency={account.currency.value} "
            f"balance={account.current_balance}{overdraft_part}"
        )

    print("\n=== ERROR LOG ===")
    for row in processor.error_log:
        print(row)

    print("\n=== AUDIT REPORT: SUSPICIOUS OPERATIONS ===")
    for record in bank.audit_log.suspicious_operations_report():
        print(
            f"[{record.level.value}] tx={record.transaction_id} "
            f"risk={record.risk_level.value if record.risk_level else '-'} "
            f"client={record.client_id} msg={record.message}"
        )

    print("\n=== AUDIT REPORT: CLIENT RISK PROFILE ===")
    for client_id, stats in bank.audit_log.client_risk_profile().items():
        print(client_id, stats)

    print("\n=== AUDIT REPORT: ERROR STATISTICS ===")
    print(bank.audit_log.error_statistics())