import csv
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .accounts import exchange_rate_to_rub
from .bank import Bank
from .enums import TransactionStatuses, TransactionTypes
from .transactions import Transaction


class ReportBuilder:
    def __init__(self, bank: Bank, processed_transactions: list[Transaction]) -> None:
        self.bank = bank
        self.processed_transactions = processed_transactions

    def build_client_report(self, client_id: str) -> dict[str, Any]:
        client = self.bank.clients_dict[client_id]
        accounts = [
            self.bank.accounts_dict[account_id]
            for account_id in client.account_ids
            if account_id in self.bank.accounts_dict
        ]
        client_transactions = self._transactions_for_accounts(client.account_ids)
        suspicious = [
            record
            for record in self.bank.audit_log.suspicious_operations_report()
            if record.client_id == client_id
        ]

        return {
            "report_type": "client",
            "generated_at": datetime.now(),
            "client": {
                "id": client.id,
                "name": f"{client.name} {client.surname}",
                "age": client.age,
                "is_locked": client.is_locked,
                "contacts": {
                    "email": client.contacts.email,
                    "phone": client.contacts.phone,
                },
            },
            "accounts": [
                {
                    "account_id": account.id,
                    "account_type": account.account_type.value,
                    "status": account.acc_status.value,
                    "currency": account.currency.value,
                    "balance_minor": account.current_balance,
                }
                for account in accounts
            ],
            "transactions_summary": {
                "total": len(client_transactions),
                "completed": sum(
                    1
                    for tx in client_transactions
                    if tx.transaction_status == TransactionStatuses.COMPLETED
                ),
                "failed": sum(
                    1
                    for tx in client_transactions
                    if tx.transaction_status == TransactionStatuses.FAILED
                ),
                "cancelled": sum(
                    1
                    for tx in client_transactions
                    if tx.transaction_status == TransactionStatuses.CANCELLED
                ),
            },
            "suspicious_operations": [
                {
                    "timestamp": record.timestamp,
                    "level": record.level.value,
                    "risk": record.risk_level.value if record.risk_level else None,
                    "message": record.message,
                    "transaction_id": record.transaction_id,
                }
                for record in suspicious
            ],
        }

    def build_bank_report(self) -> dict[str, Any]:
        statuses = defaultdict(int)
        account_type_counter = defaultdict(int)
        tx_type_counter = defaultdict(int)

        for account in self.bank.accounts_dict.values():
            statuses[account.acc_status.value] += 1
            account_type_counter[account.account_type.value] += 1

        for tx in self.processed_transactions:
            tx_type_counter[tx.transaction_type.value] += 1

        return {
            "report_type": "bank",
            "generated_at": datetime.now(),
            "clients_total": len(self.bank.clients_dict),
            "accounts_total": len(self.bank.accounts_dict),
            "total_balance_rub_minor": self.bank.get_total_balance(),
            "account_status_distribution": dict(statuses),
            "account_type_distribution": dict(account_type_counter),
            "transactions_distribution": dict(tx_type_counter),
            "top_clients_by_accounts": self.bank.get_clients_ranking()[:5],
            "audit_errors": self.bank.audit_log.error_statistics(),
        }

    def build_risk_report(self) -> dict[str, Any]:
        suspicious_records = self.bank.audit_log.suspicious_operations_report()
        by_risk_level = defaultdict(int)

        for record in suspicious_records:
            risk = record.risk_level.value if record.risk_level else "unknown"
            by_risk_level[risk] += 1

        return {
            "report_type": "risk",
            "generated_at": datetime.now(),
            "suspicious_total": len(suspicious_records),
            "by_risk_level": dict(by_risk_level),
            "client_risk_profile": self.bank.audit_log.client_risk_profile(),
            "blocked_transactions": self.bank.audit_log.error_statistics().get(
                "blocked_transactions", 0
            ),
            "records": [
                {
                    "timestamp": record.timestamp,
                    "level": record.level.value,
                    "event_type": record.event_type,
                    "client_id": record.client_id,
                    "transaction_id": record.transaction_id,
                    "risk_level": record.risk_level.value if record.risk_level else None,
                    "message": record.message,
                }
                for record in suspicious_records
            ],
        }

    def build_text_report(self, report_type: str, client_id: Optional[str] = None) -> str:
        if report_type == "client":
            if client_id is None:
                raise ValueError("client_id is required for client report")
            payload = self.build_client_report(client_id)
        elif report_type == "bank":
            payload = self.build_bank_report()
        elif report_type == "risk":
            payload = self.build_risk_report()
        else:
            raise ValueError("Unsupported report type")

        return self._dict_to_text(payload)

    def export_to_json(self, report_data: dict[str, Any], file_path: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(self._to_serializable(report_data), file, ensure_ascii=False, indent=2)

    def export_to_csv(self, report_data: dict[str, Any], file_path: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["key", "value"])
            for key, value in self._flatten_dict(report_data).items():
                writer.writerow([key, value])

    def save_charts(self, output_dir: str, client_id: Optional[str] = None) -> list[str]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        charts_paths: list[str] = []

        charts_paths.append(str(self._save_transactions_pie_chart(output_path)))
        charts_paths.append(str(self._save_account_status_bar_chart(output_path)))

        selected_client_id = client_id or next(iter(self.bank.clients_dict), None)
        if selected_client_id is not None:
            balance_chart = self._save_balance_dynamics_chart(output_path, selected_client_id)
            charts_paths.append(str(balance_chart))

        return charts_paths

    def _save_transactions_pie_chart(self, output_dir: Path) -> Path:
        counter = {
            TransactionTypes.DEPOSIT.value: 0,
            TransactionTypes.WITHDRAW.value: 0,
            TransactionTypes.TRANSFER.value: 0,
        }

        for tx in self.processed_transactions:
            counter[tx.transaction_type.value] += 1

        labels = list(counter.keys())
        values = list(counter.values())

        plt.figure(figsize=(7, 5))
        if sum(values) == 0:
            values = [1, 1, 1]
        plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        plt.title("Transactions distribution")

        path = output_dir / "transactions_pie.png"
        plt.tight_layout()
        plt.savefig(path)
        plt.close()
        return path

    def _save_account_status_bar_chart(self, output_dir: Path) -> Path:
        statuses = defaultdict(int)
        for account in self.bank.accounts_dict.values():
            statuses[account.acc_status.value] += 1

        labels = list(statuses.keys())
        values = list(statuses.values())

        plt.figure(figsize=(8, 5))
        plt.bar(labels, values, color=["#4caf50", "#ff9800", "#f44336"][: len(values)])
        plt.title("Account status distribution")
        plt.xlabel("Status")
        plt.ylabel("Count")

        path = output_dir / "accounts_status_bar.png"
        plt.tight_layout()
        plt.savefig(path)
        plt.close()
        return path

    def _save_balance_dynamics_chart(self, output_dir: Path, client_id: str) -> Path:
        client = self.bank.clients_dict[client_id]
        client_account_ids = client.account_ids

        client_transactions = sorted(
            self._transactions_for_accounts(client_account_ids), key=lambda tx: tx.created_at
        )

        cumulative_balance_rub = 0
        timeline: list[datetime] = []
        values: list[int] = []

        for tx in client_transactions:
            tx_amount_rub_minor = int(
                (
                    (Decimal(tx.amount) / Decimal("100"))
                    * exchange_rate_to_rub[tx.currency]
                    * Decimal("100")
                ).quantize(Decimal("1"))
            )

            if tx.sender_acc_id in client_account_ids:
                cumulative_balance_rub -= tx_amount_rub_minor
            if tx.receiver_acc_id in client_account_ids:
                cumulative_balance_rub += tx_amount_rub_minor

            timeline.append(tx.created_at)
            values.append(cumulative_balance_rub)

        if not timeline:
            timeline.append(datetime.now())
            values.append(0)

        plt.figure(figsize=(9, 5))
        plt.plot(timeline, values, marker="o")
        plt.title(f"Balance dynamics (RUB minor): {client.name} {client.surname}")
        plt.xlabel("Timestamp")
        plt.ylabel("Net movement in RUB minor")
        plt.xticks(rotation=30, ha="right")

        path = output_dir / f"balance_dynamics_{client_id}.png"
        plt.tight_layout()
        plt.savefig(path)
        plt.close()
        return path

    def _transactions_for_accounts(self, account_ids: set[str]) -> list[Transaction]:
        return [
            tx
            for tx in self.processed_transactions
            if tx.sender_acc_id in account_ids or tx.receiver_acc_id in account_ids
        ]

    def _dict_to_text(self, data: dict[str, Any], indent: int = 0) -> str:
        lines: list[str] = []
        spacing = " " * indent

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{spacing}{key}:")
                lines.append(self._dict_to_text(value, indent + 2))
            elif isinstance(value, list):
                lines.append(f"{spacing}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{spacing}  -")
                        lines.append(self._dict_to_text(item, indent + 4))
                    else:
                        lines.append(f"{spacing}  - {self._to_serializable(item)}")
            else:
                lines.append(f"{spacing}{key}: {self._to_serializable(value)}")

        return "\n".join(line for line in lines if line.strip())

    def _flatten_dict(
        self,
        data: dict[str, Any],
        prefix: str = "",
    ) -> dict[str, Any]:
        flat: dict[str, Any] = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.update(self._flatten_dict(value, full_key))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    item_key = f"{full_key}[{index}]"
                    if isinstance(item, dict):
                        flat.update(self._flatten_dict(item, item_key))
                    else:
                        flat[item_key] = self._to_serializable(item)
            else:
                flat[full_key] = self._to_serializable(value)

        return flat

    def _to_serializable(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._to_serializable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._to_serializable(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        if isinstance(value, Decimal):
            return str(value)
        if hasattr(value, "value"):
            return value.value
        return value