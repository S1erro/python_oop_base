from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from .accounts import AbstractAccount
from .audit import AuditLog
from .bank import Bank, Client, ClientContacts
from .enums import AccountStatuses, AccountTypes, Currencies, TransactionStatuses, TransactionTypes
from .transactions import Transaction, TransactionProcessor, TransactionQueue
from .reports import ReportBuilder


def create_demo_bank() -> tuple[Bank, list[Client], dict[str, str]]:
    bank = Bank(audit_log=AuditLog(file_path="day6_audit.log"))

    clients = [
        Client(
            name="Ivan",
            surname="Petrov",
            middlename="A",
            age=29,
            contacts=ClientContacts(email="ivan.petrov@example.com", phone="79001000001"),
        ),
        Client(
            name="Anna",
            surname="Sidorova",
            middlename="B",
            age=34,
            contacts=ClientContacts(email="anna.sidorova@example.com", phone="79001000002"),
        ),
        Client(
            name="Maksim",
            surname="Orlov",
            middlename="C",
            age=41,
            contacts=ClientContacts(email="maksim.orlov@example.com", phone="79001000003"),
        ),
        Client(
            name="Elena",
            surname="Smirnova",
            middlename="D",
            age=31,
            contacts=ClientContacts(email="elena.smirnova@example.com", phone="79001000004"),
        ),
        Client(
            name="Daniil",
            surname="Volkov",
            middlename="E",
            age=26,
            contacts=ClientContacts(email="daniil.volkov@example.com", phone="79001000005"),
        ),
        Client(
            name="Sofia",
            surname="Kuznetsova",
            middlename="F",
            age=37,
            contacts=ClientContacts(email="sofia.kuznetsova@example.com", phone="79001000006"),
        ),
    ]

    for client in clients:
        bank.add_client(client)

    accounts: dict[str, str] = {}

    def create_account(alias: str, client: Client, account_type: AccountTypes, **kwargs) -> None:
        account = bank.create_account(
            client_id=client.id,
            account_type=account_type,
            **kwargs,
        )
        accounts[alias] = account.id

    create_account("ivan_bank", clients[0], AccountTypes.BANK_ACCOUNT, currency=Currencies.RUB)
    create_account(
        "ivan_savings",
        clients[0],
        AccountTypes.SAVINGS_ACCOUNT,
        currency=Currencies.USD,
        min_balance=10_000,
        monthly_rate=Decimal("0.01"),
    )

    create_account("anna_bank", clients[1], AccountTypes.BANK_ACCOUNT, currency=Currencies.RUB)
    create_account(
        "anna_premium",
        clients[1],
        AccountTypes.PREMIUM_ACCOUNT,
        currency=Currencies.EUR,
        overdraft_limit=120_000,
        available_overdraft=120_000,
        commission=Decimal("0.01"),
    )

    create_account("maksim_bank", clients[2], AccountTypes.BANK_ACCOUNT, currency=Currencies.USD)
    create_account("maksim_invest", clients[2], AccountTypes.INVESTMENT_ACCOUNT, currency=Currencies.RUB)

    create_account("elena_bank", clients[3], AccountTypes.BANK_ACCOUNT, currency=Currencies.RUB)
    create_account(
        "elena_savings",
        clients[3],
        AccountTypes.SAVINGS_ACCOUNT,
        currency=Currencies.EUR,
        min_balance=8_000,
        monthly_rate=Decimal("0.007"),
    )

    create_account("daniil_bank", clients[4], AccountTypes.BANK_ACCOUNT, currency=Currencies.KZT)
    create_account(
        "daniil_premium",
        clients[4],
        AccountTypes.PREMIUM_ACCOUNT,
        currency=Currencies.RUB,
        overdraft_limit=80_000,
        available_overdraft=80_000,
        commission=Decimal("0.02"),
    )

    create_account("sofia_bank", clients[5], AccountTypes.BANK_ACCOUNT, currency=Currencies.CNY)
    create_account("sofia_invest", clients[5], AccountTypes.INVESTMENT_ACCOUNT, currency=Currencies.USD)

    initial_balances = {
        "ivan_bank": 420_000,
        "ivan_savings": 180_000,
        "anna_bank": 350_000,
        "anna_premium": 260_000,
        "maksim_bank": 300_000,
        "maksim_invest": 120_000,
        "elena_bank": 270_000,
        "elena_savings": 90_000,
        "daniil_bank": 600_000,
        "daniil_premium": 150_000,
        "sofia_bank": 200_000,
        "sofia_invest": 170_000,
    }

    for alias, balance in initial_balances.items():
        bank.accounts_dict[accounts[alias]].current_balance = balance

    bank.accounts_dict[accounts["elena_savings"]].acc_status = AccountStatuses.FROZEN
    bank.accounts_dict[accounts["maksim_invest"]].acc_status = AccountStatuses.CLOSED

    return bank, clients, accounts


def build_transactions(accounts: dict[str, str]) -> list[Transaction]:
    now = datetime.now().replace(microsecond=0)
    night_time = now.replace(hour=1, minute=20, second=0)

    return [
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=6_000, currency=Currencies.RUB, sender_acc_id=accounts["ivan_bank"], receiver_acc_id=accounts["anna_bank"], first_priority=True),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=4_500, currency=Currencies.USD, sender_acc_id=accounts["maksim_bank"], receiver_acc_id=accounts["ivan_savings"]),
        Transaction(transaction_type=TransactionTypes.DEPOSIT, amount=12_000, currency=Currencies.EUR, receiver_acc_id=accounts["anna_premium"]),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=5_000, currency=Currencies.KZT, sender_acc_id=accounts["daniil_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=3_000, currency=Currencies.CNY, sender_acc_id=accounts["sofia_bank"], receiver_acc_id=accounts["daniil_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=8_000, currency=Currencies.RUB, sender_acc_id=accounts["anna_bank"], receiver_acc_id=accounts["elena_bank"], scheduled_at=now + timedelta(seconds=1)),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=7_000, currency=Currencies.USD, sender_acc_id=accounts["ivan_savings"], receiver_acc_id=accounts["sofia_invest"]),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=10_000, currency=Currencies.RUB, sender_acc_id=accounts["ivan_bank"]),
        Transaction(transaction_type=TransactionTypes.DEPOSIT, amount=11_000, currency=Currencies.RUB, receiver_acc_id=accounts["elena_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=4_000, currency=Currencies.EUR, sender_acc_id=accounts["anna_premium"], receiver_acc_id=accounts["maksim_bank"], first_priority=True),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=5_500, currency=Currencies.RUB, sender_acc_id=accounts["daniil_premium"], receiver_acc_id=accounts["ivan_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=2_500, currency=Currencies.USD, sender_acc_id=accounts["sofia_invest"], receiver_acc_id=accounts["maksim_bank"]),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=9_000, currency=Currencies.CNY, sender_acc_id=accounts["sofia_bank"]),
        Transaction(transaction_type=TransactionTypes.DEPOSIT, amount=4_000, currency=Currencies.KZT, receiver_acc_id=accounts["daniil_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=1_000, currency=Currencies.RUB, sender_acc_id=accounts["elena_bank"], receiver_acc_id=accounts["ivan_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=6_700, currency=Currencies.USD, sender_acc_id=accounts["maksim_bank"], receiver_acc_id=accounts["anna_premium"]),
        Transaction(transaction_type=TransactionTypes.DEPOSIT, amount=9_300, currency=Currencies.USD, receiver_acc_id=accounts["ivan_savings"]),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=3_500, currency=Currencies.EUR, sender_acc_id=accounts["anna_premium"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=4_200, currency=Currencies.KZT, sender_acc_id=accounts["daniil_bank"], receiver_acc_id=accounts["sofia_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=7_700, currency=Currencies.RUB, sender_acc_id=accounts["ivan_bank"], receiver_acc_id=accounts["daniil_premium"]),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=8_500, currency=Currencies.RUB, sender_acc_id=accounts["elena_savings"]),
        Transaction(transaction_type=TransactionTypes.DEPOSIT, amount=4_000, currency=Currencies.RUB, receiver_acc_id=accounts["maksim_invest"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=900_000, currency=Currencies.RUB, sender_acc_id=accounts["ivan_bank"], receiver_acc_id=accounts["sofia_invest"], created_at=night_time),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=2_000, currency=Currencies.RUB, sender_acc_id=accounts["anna_bank"], receiver_acc_id=accounts["sofia_invest"], created_at=night_time + timedelta(minutes=1)),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=2_100, currency=Currencies.RUB, sender_acc_id=accounts["anna_bank"], receiver_acc_id=accounts["sofia_invest"], created_at=night_time + timedelta(minutes=2)),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=2_200, currency=Currencies.RUB, sender_acc_id=accounts["anna_bank"], receiver_acc_id=accounts["sofia_invest"], created_at=night_time + timedelta(minutes=3)),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=500_000, currency=Currencies.RUB, sender_acc_id=accounts["daniil_bank"], receiver_acc_id=accounts["elena_bank"], created_at=night_time + timedelta(minutes=4)),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=350_000, currency=Currencies.USD, sender_acc_id=accounts["sofia_invest"], receiver_acc_id=accounts["anna_bank"], created_at=night_time + timedelta(minutes=5)),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=5_000_000, currency=Currencies.RUB, sender_acc_id=accounts["anna_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=12_000, currency=Currencies.USD, sender_acc_id="unknown_sender", receiver_acc_id=accounts["ivan_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=7_000, currency=Currencies.CNY, sender_acc_id=accounts["sofia_bank"], receiver_acc_id="unknown_receiver"),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=7_500, currency=Currencies.RUB, sender_acc_id=accounts["maksim_invest"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=8_000, currency=Currencies.RUB, sender_acc_id=accounts["elena_savings"], receiver_acc_id=accounts["anna_bank"]),
        Transaction(transaction_type=TransactionTypes.DEPOSIT, amount=2_000, currency=Currencies.RUB, receiver_acc_id=accounts["ivan_bank"]),
        Transaction(transaction_type=TransactionTypes.TRANSFER, amount=2_300, currency=Currencies.USD, sender_acc_id=accounts["ivan_savings"], receiver_acc_id=accounts["maksim_bank"]),
        Transaction(transaction_type=TransactionTypes.WITHDRAW, amount=2_500, currency=Currencies.KZT, sender_acc_id=accounts["daniil_bank"]),
    ]


def print_user_scenarios(
    bank: Bank,
    client: Client,
    processed_transactions: list[Transaction],
) -> None:
    print("\n=== 👤 Пользовательский сценарий ===")
    print(f"Клиент: {client.name} {client.surname} ({client.id})")

    print("\n💰 Счета клиента:")
    for account_id in client.account_ids:
        account = bank.accounts_dict[account_id]
        print(
            f"- {account.account_type.value} | id={account.id} | "
            f"status={account.acc_status.value} | balance={account.current_balance} {account.currency.value}"
        )

    print("\n📜 История операций клиента:")
    for tx in processed_transactions:
        if tx.sender_acc_id in client.account_ids or tx.receiver_acc_id in client.account_ids:
            print(
                f"- {tx.id[:8]} | {tx.transaction_type.value:<8} | "
                f"{tx.transaction_status.value:<9} | amount={tx.amount} {tx.currency.value}"
            )

    print("\n⚠️ Подозрительные операции клиента:")
    suspicious_records = [
        record
        for record in bank.audit_log.suspicious_operations_report()
        if record.client_id == client.id
    ]

    if not suspicious_records:
        print("- Нет подозрительных операций")
        return

    for record in suspicious_records:
        print(
            f"- [{record.level.value}] tx={record.transaction_id[:8] if record.transaction_id else '-'} "
            f"risk={record.risk_level.value if record.risk_level else '-'} msg={record.message}"
        )


def print_reports(bank: Bank, processed_transactions: list[Transaction]) -> None:
    print("\n=== 📊 Отчёты ===")

    print("\n🏆 Топ-3 клиентов по числу счетов:")
    for rank, row in enumerate(bank.get_clients_ranking()[:3], start=1):
        print(f"{rank}. {row['client']} — счетов: {row['acc_count']}")

    total = len(processed_transactions)
    completed = sum(1 for tx in processed_transactions if tx.transaction_status == TransactionStatuses.COMPLETED)
    failed = sum(1 for tx in processed_transactions if tx.transaction_status == TransactionStatuses.FAILED)
    cancelled = sum(1 for tx in processed_transactions if tx.transaction_status == TransactionStatuses.CANCELLED)

    by_type: dict[str, int] = {
        TransactionTypes.DEPOSIT.value: 0,
        TransactionTypes.WITHDRAW.value: 0,
        TransactionTypes.TRANSFER.value: 0,
    }
    for tx in processed_transactions:
        by_type[tx.transaction_type.value] += 1

    print("\n📈 Статистика транзакций:")
    print(f"- Всего: {total}")
    print(f"- Успешные: {completed}")
    print(f"- Отклоненные/ошибочные: {failed}")
    print(f"- Отмененные: {cancelled}")
    print(f"- По типам: {by_type}")
    print(f"- Ошибки аудита: {bank.audit_log.error_statistics()}")

    print(f"\n💎 Общий баланс банка (в копейках RUB): {bank.get_total_balance()}")


def run_day6_demo() -> None:
    print("=== 📘 День 6: Демонстрационная программа ===")
    AbstractAccount.ensure_operation_allowed_now = staticmethod(lambda: None)

    bank, clients, accounts = create_demo_bank()
    transactions = build_transactions(accounts)

    print("\nИнициализация:")
    print(f"- 🏦 Банк создан")
    print(f"- 👥 Клиентов: {len(clients)}")
    print(f"- 💳 Счетов: {len(bank.accounts_dict)}")
    print(f"- 🔄 Запланировано транзакций: {len(transactions)}")

    queue = TransactionQueue()
    processor = TransactionProcessor(external_transfer_commission=Decimal("0.025"))

    print("\n📝 Добавление транзакций в очередь:")
    for transaction in transactions:
        queue.add_transaction(transaction)
        print(
            f"- queued tx={transaction.id[:8]} type={transaction.transaction_type.value} "
            f"amount={transaction.amount} {transaction.currency.value}"
        )

    queue.cancel_transaction(transactions[-2].id)
    print(f"- 🚫 tx={transactions[-2].id[:8]} отменена до обработки")

    print("\n⚙️ Обработка очереди:")
    processed_transactions = bank.process_transactions_with_risk(queue, processor)
    for tx in processed_transactions:
        if tx.transaction_status == TransactionStatuses.COMPLETED:
            print(f"✅ tx={tx.id[:8]} исполнена")
        elif tx.transaction_status == TransactionStatuses.CANCELLED:
            print(f"🚫 tx={tx.id[:8]} отменена")
        else:
            print(f"🚫 tx={tx.id[:8]} отклонена: {tx.failure_reason}")

    print_user_scenarios(bank, clients[0], processed_transactions)
    print_reports(bank, processed_transactions)


def run_day7_demo() -> None:
    print("\n=== 📘 День 7: Система отчётности и визуализации ===")
    AbstractAccount.ensure_operation_allowed_now = staticmethod(lambda: None)

    bank, clients, accounts = create_demo_bank()
    transactions = build_transactions(accounts)

    queue = TransactionQueue()
    processor = TransactionProcessor(external_transfer_commission=Decimal("0.025"))

    for transaction in transactions:
        queue.add_transaction(transaction)

    processed_transactions = bank.process_transactions_with_risk(queue, processor)
    report_builder = ReportBuilder(bank=bank, processed_transactions=processed_transactions)

    output_dir = Path("reports/day7")
    output_dir.mkdir(parents=True, exist_ok=True)

    client_id = clients[0].id
    report_specs = [
        ("client", report_builder.build_client_report(client_id), "client_report"),
        ("bank", report_builder.build_bank_report(), "bank_report"),
        ("risk", report_builder.build_risk_report(), "risk_report"),
    ]

    for report_type, report_data, file_stem in report_specs:
        txt = report_builder.build_text_report(report_type, client_id=client_id)
        text_path = output_dir / f"{file_stem}.txt"
        with text_path.open("w", encoding="utf-8") as file:
            file.write(txt)

        report_builder.export_to_json(report_data, str(output_dir / f"{file_stem}.json"))
        report_builder.export_to_csv(report_data, str(output_dir / f"{file_stem}.csv"))

    chart_paths = report_builder.save_charts(str(output_dir), client_id=client_id)

    print("\n✅ Отчёты сформированы:")
    for _, _, file_stem in report_specs:
        print(f"- {output_dir / f'{file_stem}.txt'}")
        print(f"- {output_dir / f'{file_stem}.json'}")
        print(f"- {output_dir / f'{file_stem}.csv'}")

    print("\n📊 Графики сохранены:")
    for chart in chart_paths:
        print(f"- {chart}")


if __name__ == "__main__":
    run_day6_demo()
    run_day7_demo()
