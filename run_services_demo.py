from datetime import datetime
from typing import Callable, Dict, List

# Импорты компонентов сервисов
from booking_service.booking_facade import BookingOrchestrationFacade
from booking_service.appointment_state import AppointmentLifecycle
from loyalty_service.cached_rules_proxy import DatabaseRulesProvider, CachedRulesProxy
from loyalty_service.pricing_strategy import TierAccumulativeStrategy
from loyalty_service.transaction_factory import AccrualTransactionCreator
from loyalty_service.loyalty_observer import LoyaltyAppointmentCompletedConsumer
from notification_service.senders_adapter import VendorSmsSdk, SmsAdapter
from notification_service.event_listener import NotificationAppointmentCompletedConsumer


# Эмуляция Message Broker (RabbitMQ / Kafka)
class MessageBroker:
    def __init__(self):
        self._topics: Dict[str, List[Callable]] = {}

    def subscribe(self, topic: str, handler: Callable):
        self._topics.setdefault(topic, []).append(handler)

    def publish(self, topic: str, payload: dict):
        print(f"\n[Message Broker] Событие опубликовано в тему '{topic}'")
        for handler in self._topics.get(topic, []):
            handler(payload)


# Эмуляция REST-клиента для Booking Service -> Loyalty Service
class MockLoyaltyRestClient:
    def __init__(self, strategy: TierAccumulativeStrategy):
        self._strategy = strategy

    def calculate_discount(self, client_id: str, base_price: float) -> dict:
        # Допустим, у клиента client-101 накоплено 35 000 руб. (уровень Gold = 10%)
        discount = self._strategy.calculate(base_price=base_price, total_spent=35000.0)
        return {"discount_amount": discount}


if __name__ == "__main__":
    broker = MessageBroker()

    # Запуск Loyalty Service
    rules_proxy = CachedRulesProxy(DatabaseRulesProvider())
    tier_strategy = TierAccumulativeStrategy(rules_provider=rules_proxy)
    accrual_creator = AccrualTransactionCreator()
    loyalty_consumer = LoyaltyAppointmentCompletedConsumer(accrual_creator)

    # Запуск Notification Service
    sms_adapter = SmsAdapter(VendorSmsSdk())
    notification_consumer = NotificationAppointmentCompletedConsumer(sms_adapter)

    # Подписка микросервисов на события брокера
    broker.subscribe("appointment.completed", loyalty_consumer.handle_event)
    broker.subscribe("appointment.completed", notification_consumer.handle_event)

    # Инициализация Booking Service
    loyalty_api_client = MockLoyaltyRestClient(tier_strategy)
    facade = BookingOrchestrationFacade(loyalty_api_client, broker)

    print("=== ЭТАП 1: Создание записи через Booking Service ===")
    appointment = facade.create_and_book(
        appointment_id="APT-2026-001",
        client_id="client-101",
        master_id="master-05",
        service_id="service-10",
        dt=datetime(2026, 11, 25, 14, 0),
        base_price=3000.0,
        duration=60,
        points_to_redeem=400  # Списание баллов
    )
    print(f"Запись сохранена: базовый прайс = {appointment.base_price} ₽, "
          f"скидка = {appointment.discount_amount} ₽, "
          f"списано бонусов = {appointment.points_redeemed}, "
          f"итоговый чек = {appointment.final_price} ₽")

    print("\n=== ЭТАП 2: Жизненный цикл записи (State) ===")
    def on_complete_callback(apt_id: str):
        broker.publish("appointment.completed", {
            "appointment_id": apt_id,
            "client_id": appointment.client_id,
            "final_price": appointment.final_price,
            "phone": "+7 (912) 888-77-66"
        })

    lifecycle = AppointmentLifecycle(appointment.id, on_completed_callback=on_complete_callback)
    lifecycle.confirm()
    lifecycle.complete()
