from datetime import datetime
from booking_service.appointment_builder import AppointmentBuilder, Appointment


class BookingOrchestrationFacade:
    def __init__(self, loyalty_client, event_bus):
        self._loyalty_client = loyalty_client
        self._event_bus = event_bus

    def create_and_book(
        self,
        appointment_id: str,
        client_id: str,
        master_id: str,
        service_id: str,
        dt: datetime,
        base_price: float,
        duration: int,
        points_to_redeem: int
    ) -> Appointment:
        # 1. Запрос в Loyalty Service на расчет скидки (REST/gRPC клиент)
        pricing = self._loyalty_client.calculate_discount(client_id, base_price)
        
        # 2. Сборка объекта через Builder
        appointment = (
            AppointmentBuilder(appointment_id)
            .for_client(client_id)
            .with_master_and_service(master_id, service_id, base_price, duration)
            .at_time(dt)
            .apply_discount(pricing["discount_amount"])
            .redeem_points(points_to_redeem)
            .build()
        )

        # 3. Публикация события о бронировании
        self._event_bus.publish("appointment.created", {
            "appointment_id": appointment.id,
            "client_id": appointment.client_id,
            "final_price": appointment.final_price
        })

        return appointment