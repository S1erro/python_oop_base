from decimal import Decimal

from .accounts import (
    AbstractAccount,
    BankAccount,
    Bonds,
    InvestmentAccount,
    InvestmentPortfolio,
    PremiumAccount,
    SavingsAccount,
    Stocks,
    exchange_rate_to_rub,
)
from .bank import Bank, Client, ClientContacts
from .enums import (
    AccountStatuses,
    AccountTypes,
    AuditLevels,
    Currencies,
    RiskLevels,
)
from .exceptions import (
    AccountClosedError,
    AccountFrozenError,
    ClientIdUsed,
    InappropriateAge,
    InsufficientFundsError,
    InvalidOperationError,
)
from .audit import AuditLog, AuditRecord, RiskAnalyzer
from .transactions import run_transactions_demo

__all__ = [
    "AccountStatuses",
    "Currencies",
    "AccountTypes",
    "AuditLevels",
    "RiskLevels",
    "AuditRecord",
    "AuditLog",
    "RiskAnalyzer",
    "InvestmentPortfolio",
    "Stocks",
    "Bonds",
    "AbstractAccount",
    "BankAccount",
    "SavingsAccount",
    "PremiumAccount",
    "InvestmentAccount",
    "exchange_rate_to_rub",
    "ClientContacts",
    "Client",
    "Bank",
    "AccountFrozenError",
    "AccountClosedError",
    "InsufficientFundsError",
    "InvalidOperationError",
    "InappropriateAge",
    "ClientIdUsed",
]


def run_bank_tests() -> None:
    print()
    AbstractAccount.ensure_operation_allowed_now = staticmethod(lambda: None)

    print("\n=== BANK INTEGRATION TESTS ===")
    bank = Bank()

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

    acc_1.deposit(20_000)
    acc_1.withdraw(5_000)
    acc_2.deposit(30_000)
    acc_3.deposit(15_000)
    print("[OK] Deposit/withdraw operations")

    assert bank.authenticate_client(client_1.id, "0000000000") is False
    assert bank.authenticate_client(client_1.id, "0000000000") is False
    assert bank.authenticate_client(client_1.id, "0000000000") is False
    assert bank.clients_dict[client_1.id].is_locked is True
    print("[OK] 3 failed auth attempts -> client locked")

    assert bank.authenticate_client(client_2.id, "9999888877") is True
    print("[OK] Successful auth")

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

    ranking = bank.get_clients_ranking()
    total_balance = bank.get_total_balance()

    print("\n--- Ranking ---")
    for row in ranking:
        print(row)

    print(f"\nTotal balance in RUB kopecks: {total_balance}")
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    run_bank_tests()
    print("\n=== TRANSACTIONS DEMO ===")
    run_transactions_demo()
