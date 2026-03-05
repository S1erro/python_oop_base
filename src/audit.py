from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import AuditLevels, RiskLevels, TransactionTypes


class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    level: AuditLevels
    event_type: str
    message: str
    transaction_id: Optional[str] = None
    client_id: Optional[str] = None
    risk_level: Optional[RiskLevels] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditLog(BaseModel):
    file_path: str = "audit.log"
    records: list[AuditRecord] = Field(default_factory=list)

    def log(
        self,
        level: AuditLevels,
        event_type: str,
        message: str,
        transaction_id: Optional[str] = None,
        client_id: Optional[str] = None,
        risk_level: Optional[RiskLevels] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditRecord:
        record = AuditRecord(
            level=level,
            event_type=event_type,
            message=message,
            transaction_id=transaction_id,
            client_id=client_id,
            risk_level=risk_level,
            metadata=metadata or {},
        )
        self.records.append(record)
        self._append_to_file(record)
        return record

    def _append_to_file(self, record: AuditRecord) -> None:
        metadata_repr = ", ".join(
            [f"{key}={value}" for key, value in record.metadata.items()]
        )
        line = (
            f"{record.timestamp.isoformat(timespec='seconds')} "
            f"[{record.level.value.upper()}] "
            f"event={record.event_type} tx={record.transaction_id} "
            f"client={record.client_id} risk={record.risk_level.value if record.risk_level else None} "
            f"msg={record.message} meta={metadata_repr}\n"
        )
        with open(self.file_path, "a", encoding="utf-8") as file:
            file.write(line)

    def filter_records(
        self,
        level: Optional[AuditLevels] = None,
        event_type: Optional[str] = None,
        client_id: Optional[str] = None,
        risk_level: Optional[RiskLevels] = None,
    ) -> list[AuditRecord]:
        result = self.records
        if level is not None:
            result = [record for record in result if record.level == level]
        if event_type is not None:
            result = [record for record in result if record.event_type == event_type]
        if client_id is not None:
            result = [record for record in result if record.client_id == client_id]
        if risk_level is not None:
            result = [record for record in result if record.risk_level == risk_level]
        return result

    def suspicious_operations_report(self) -> list[AuditRecord]:
        return [
            record
            for record in self.records
            if record.event_type == "suspicious_transaction"
            or record.event_type == "blocked_transaction"
        ]

    def client_risk_profile(self) -> dict[str, dict[str, int]]:
        profile: dict[str, dict[str, int]] = {}

        for record in self.suspicious_operations_report():
            if record.client_id is None:
                continue

            if record.client_id not in profile:
                profile[record.client_id] = {
                    "suspicious_count": 0,
                    "medium_risk_count": 0,
                    "high_risk_count": 0,
                }

            profile[record.client_id]["suspicious_count"] += 1
            if record.risk_level == RiskLevels.MEDIUM:
                profile[record.client_id]["medium_risk_count"] += 1
            if record.risk_level == RiskLevels.HIGH:
                profile[record.client_id]["high_risk_count"] += 1

        return profile

    def error_statistics(self) -> dict[str, int]:
        errors = [
            record
            for record in self.records
            if record.level in {AuditLevels.ERROR, AuditLevels.CRITICAL}
        ]
        stats: dict[str, int] = {
            "total_errors": len(errors),
            "transaction_errors": 0,
            "blocked_transactions": 0,
        }

        for record in errors:
            if record.event_type == "transaction_error":
                stats["transaction_errors"] += 1
            if record.event_type == "blocked_transaction":
                stats["blocked_transactions"] += 1

        return stats


class RiskAnalyzer(BaseModel):
    large_amount_threshold: int = 300_000
    frequent_operations_threshold: int = 3
    frequent_operations_window: timedelta = timedelta(minutes=10)
    operation_history: dict[str, list[datetime]] = Field(default_factory=dict)
    known_receivers_by_sender: dict[str, set[str]] = Field(default_factory=dict)

    def analyze(
        self,
        transaction: Any,
        account_to_client: dict[str, str],
    ) -> tuple[RiskLevels, list[str], Optional[str]]:
        sender_id = transaction.sender_acc_id
        receiver_id = transaction.receiver_acc_id
        tx_time = transaction.created_at
        reasons: list[str] = []

        if transaction.amount >= self.large_amount_threshold:
            reasons.append("large_amount")

        if sender_id is not None:
            history = self.operation_history.setdefault(sender_id, [])
            threshold_time = tx_time - self.frequent_operations_window
            history[:] = [operation_time for operation_time in history if operation_time >= threshold_time]
            if len(history) >= self.frequent_operations_threshold:
                reasons.append("frequent_operations")
            history.append(tx_time)

        if (
            transaction.transaction_type == TransactionTypes.TRANSFER
            and sender_id is not None
            and receiver_id is not None
        ):
            known_receivers = self.known_receivers_by_sender.setdefault(sender_id, set())
            if receiver_id not in known_receivers:
                reasons.append("new_receiver")
                known_receivers.add(receiver_id)

        if tx_time.hour >= 23 or tx_time.hour < 6:
            reasons.append("night_operation")

        risk_level = self._resolve_risk_level(reasons)
        client_id = account_to_client.get(sender_id or "") or account_to_client.get(receiver_id or "")
        return risk_level, reasons, client_id

    @staticmethod
    def _resolve_risk_level(reasons: list[str]) -> RiskLevels:
        if len(reasons) >= 3:
            return RiskLevels.HIGH
        if len(reasons) >= 1:
            return RiskLevels.MEDIUM
        return RiskLevels.LOW

    @staticmethod
    def is_dangerous(risk_level: RiskLevels) -> bool:
        return risk_level == RiskLevels.HIGH