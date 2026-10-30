import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BonusTransaction:
    id: str
    client_id: str
    appointment_id: Optional[str]
    tx_type: str
    points: int
    balance_before: int
    balance_after: int


class TransactionCreator(ABC):
    @abstractmethod
    def create(self, client_id: str, points: int, current_balance: int, appointment_id: Optional[str] = None) -> BonusTransaction:
        pass


class AccrualTransactionCreator(TransactionCreator):
    def create(self, client_id: str, points: int, current_balance: int, appointment_id: Optional[str] = None) -> BonusTransaction:
        return BonusTransaction(
            id=str(uuid.uuid4())[:8],
            client_id=client_id,
            appointment_id=appointment_id,
            tx_type="ACCRUAL",
            points=points,
            balance_before=current_balance,
            balance_after=current_balance + points
        )


class RedemptionTransactionCreator(TransactionCreator):
    def create(self, client_id: str, points: int, current_balance: int, appointment_id: Optional[str] = None) -> BonusTransaction:
        if points > current_balance:
            raise ValueError("Недостаточно бонусов на счете")
        return BonusTransaction(
            id=str(uuid.uuid4())[:8],
            client_id=client_id,
            appointment_id=appointment_id,
            tx_type="REDEMPTION",
            points=-points,
            balance_before=current_balance,
            balance_after=current_balance - points
        )