from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Appointment:
    id: str
    client_id: str
    master_id: str
    service_id: str
    scheduled_datetime: datetime
    duration_minutes: int
    base_price: float
    discount_amount: float
    points_redeemed: int
    final_price: float
    status: str = "CREATED"


class AppointmentBuilder:
    def __init__(self, appointment_id: str):
        self._id = appointment_id
        self._client_id: Optional[str] = None
        self._master_id: Optional[str] = None
        self._service_id: Optional[str] = None
        self._datetime: Optional[datetime] = None
        self._duration: int = 60
        self._base_price: float = 0.0
        self._discount_amount: float = 0.0
        self._points_to_redeem: int = 0

    def for_client(self, client_id: str):
        self._client_id = client_id
        return self

    def with_master_and_service(self, master_id: str, service_id: str, price: float, duration: int):
        self._master_id = master_id
        self._service_id = service_id
        self._base_price = price
        self._duration = duration
        return self

    def at_time(self, dt: datetime):
        self._datetime = dt
        return self

    def apply_discount(self, discount_amount: float):
        self._discount_amount = discount_amount
        return self

    def redeem_points(self, points: int):
        self._points_to_redeem = points
        return self

    def build(self) -> Appointment:
        if not all([self._client_id, self._master_id, self._service_id, self._datetime]):
            raise ValueError("Не заполнены обязательные параметры бронирования")

        price_after_discount = self._base_price - self._discount_amount
        # Правило ТЗ: списание бонусов не более 50% стоимости после скидки
        max_allowed_points = int(price_after_discount * 0.5)
        points_used = min(self._points_to_redeem, max_allowed_points)
        final_price = price_after_discount - points_used

        return Appointment(
            id=self._id,
            client_id=self._client_id,
            master_id=self._master_id,
            service_id=self._service_id,
            scheduled_datetime=self._datetime,
            duration_minutes=self._duration,
            base_price=self._base_price,
            discount_amount=self._discount_amount,
            points_redeemed=points_used,
            final_price=final_price
        )