import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Добавляем папку booking_app в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from appointment_builder import AppointmentBuilder
from appointment_state import (
    AppointmentLifecycle,
    CreatedState,
    CompletedState,
)
from booking_facade import BookingOrchestrationFacade


class TestAppointmentBuilder(unittest.TestCase):
    """Unit-тесты для паттерна Builder (AppointmentBuilder)."""

    def setUp(self):
        self.dt = datetime(2026, 11, 25, 14, 0)

    def _create_base_builder(self, apt_id="APT-001"):
        return (
            AppointmentBuilder(apt_id)
            .for_client("client-101")
            .with_master_and_service("master-05", "service-10", price=3000.0, duration=60)
            .at_time(self.dt)
        )

    def test_build_valid_appointment_calculates_final_price(self):
        """[Положительный] Расчет итоговой цены со скидкой и списанием баллов"""
        builder = self._create_base_builder().apply_discount(300.0).redeem_points(400)
        apt = builder.build()

        self.assertEqual(apt.id, "APT-001")
        self.assertEqual(apt.base_price, 3000.0)
        self.assertEqual(apt.discount_amount, 300.0)
        self.assertEqual(apt.points_redeemed, 400)
        self.assertEqual(apt.final_price, 2300.0)
        self.assertEqual(apt.status, "CREATED")
        print(f"  -> Итог: база={apt.base_price}, скидка={apt.discount_amount}, баллы={apt.points_redeemed}, чек={apt.final_price} руб.")

    def test_build_points_exceeding_half_price_clamped_to_50_percent(self):
        """[Граница] Попытка списать >50% баллов обрезается ровно до 50%"""
        builder = (
            AppointmentBuilder("APT-002")
            .for_client("client-101")
            .with_master_and_service("master-05", "service-10", price=2500.0, duration=60)
            .at_time(self.dt)
            .apply_discount(500.0)
            .redeem_points(1500)
        )
        apt = builder.build()

        self.assertEqual(apt.points_redeemed, 1000)
        self.assertEqual(apt.final_price, 1000.0)
        print(f"  -> Запрошено 1500 баллов при цене 2000 руб., списано={apt.points_redeemed}, чек={apt.final_price} руб.")

    def test_build_zero_discount_and_zero_points(self):
        """[Граница] Нулевая скидка и 0 баллов оставляют базовую цену"""
        builder = self._create_base_builder().apply_discount(0.0).redeem_points(0)
        apt = builder.build()

        self.assertEqual(apt.points_redeemed, 0)
        self.assertEqual(apt.final_price, 3000.0)
        print(f"  -> Скидка=0, баллы=0, итоговый чек={apt.final_price} руб.")

    def test_build_missing_required_fields_raises_value_error(self):
        """[Пустота / Исключение] Отсутствие обязательных полей вызывает ValueError"""
        builder = AppointmentBuilder("APT-EMPTY")
        with self.assertRaises(ValueError) as ctx:
            builder.build()
        print(f"  -> Поймано ожидаемое исключение: {ctx.exception}")

    def test_build_empty_client_id_raises_value_error(self):
        """[Пустота / Исключение] Пустая строка в client_id вызывает ValueError"""
        builder = (
            AppointmentBuilder("APT-003")
            .for_client("")
            .with_master_and_service("master-05", "service-10", price=1000.0, duration=30)
            .at_time(self.dt)
        )
        with self.assertRaises(ValueError) as ctx:
            builder.build()
        print(f"  -> Поймано ожидаемое исключение при пустом client_id: {ctx.exception}")


class TestAppointmentState(unittest.TestCase):
    """Unit-тесты для паттерна State (AppointmentLifecycle)."""

    def test_lifecycle_confirm_and_complete_triggers_callback(self):
        """[Положительный] Переходы CREATED -> CONFIRMED -> COMPLETED и вызов callback"""
        callback_mock = MagicMock()
        lifecycle = AppointmentLifecycle("APT-100", on_completed_callback=callback_mock)

        lifecycle.confirm()
        lifecycle.complete()

        self.assertIsInstance(lifecycle.state, CompletedState)
        self.assertEqual(lifecycle.status_name, "COMPLETED")
        callback_mock.assert_called_once_with("APT-100")
        print(f"  -> Финальный статус={lifecycle.status_name}, callback вызван 1 раз")

    def test_complete_from_created_raises_value_error(self):
        """[Исключение] Запрет завершения неподтвержденной записи (CREATED -> COMPLETED)"""
        lifecycle = AppointmentLifecycle("APT-101")
        with self.assertRaises(ValueError) as ctx:
            lifecycle.complete()
        print(f"  -> Поймано ожидаемое исключение: {ctx.exception}")

    def test_cancel_from_completed_raises_value_error(self):
        """[Исключение] Запрет отмены уже выполненной записи (COMPLETED -> CANCELLED)"""
        lifecycle = AppointmentLifecycle("APT-102", initial_status="COMPLETED")
        with self.assertRaises(ValueError) as ctx:
            lifecycle.cancel()
        print(f"  -> Поймано ожидаемое исключение: {ctx.exception}")

    def test_confirm_from_cancelled_raises_value_error(self):
        """[Исключение] Запрет подтверждения отмененной записи (CANCELLED -> CONFIRMED)"""
        lifecycle = AppointmentLifecycle("APT-103", initial_status="CANCELLED")
        with self.assertRaises(ValueError) as ctx:
            lifecycle.confirm()
        print(f"  -> Поймано ожидаемое исключение: {ctx.exception}")

    def test_unknown_initial_status_defaults_to_created_state(self):
        """[Пустота / Граница] Пустой начальный статус сбрасывается в CreatedState"""
        lifecycle = AppointmentLifecycle("APT-104", initial_status="")
        self.assertIsInstance(lifecycle.state, CreatedState)
        print(f"  -> При пустом статусе установлено состояние: {lifecycle.state.__class__.__name__}")


class TestBookingFacade(unittest.TestCase):
    """Unit-тесты для паттерна Facade с мокированием внешних зависимостей."""

    def setUp(self):
        self.loyalty_mock = MagicMock()
        self.event_bus_mock = MagicMock()
        self.facade = BookingOrchestrationFacade(self.loyalty_mock, self.event_bus_mock)
        self.dt = datetime(2026, 11, 25, 15, 0)

    def test_create_and_book_calls_loyalty_redeems_points_and_publishes_event(self):
        """[Положительный / Mock] Фасад запрашивает скидку, списывает баллы и шлет событие"""
        self.loyalty_mock.calculate_discount.return_value = {"discount_amount": 300.0}

        apt = self.facade.create_and_book(
            appointment_id="APT-200",
            client_id="client-101",
            master_id="master-05",
            service_id="service-10",
            dt=self.dt,
            base_price=3000.0,
            duration=60,
            points_to_redeem=200,
        )

        self.assertEqual(apt.final_price, 2500.0)
        self.loyalty_mock.calculate_discount.assert_called_once_with("client-101", 3000.0)
        self.loyalty_mock.redeem_points.assert_called_once_with(
            client_id="client-101", points=200, appointment_id="APT-200"
        )
        self.event_bus_mock.publish.assert_called_once_with(
            "appointment.created",
            {"appointment_id": "APT-200", "client_id": "client-101", "final_price": 2500.0},
        )
        print(f"  -> Фасад отработал: итого={apt.final_price} руб., все моки вызваны по 1 разу")

    def test_create_and_book_zero_points_does_not_call_redeem(self):
        """[Граница / Mock] При 0 баллов метод redeem_points не вызывается"""
        self.loyalty_mock.calculate_discount.return_value = {"discount_amount": 0.0}

        apt = self.facade.create_and_book(
            appointment_id="APT-201",
            client_id="client-102",
            master_id="master-05",
            service_id="service-10",
            dt=self.dt,
            base_price=1000.0,
            duration=60,
            points_to_redeem=0,
        )

        self.assertEqual(apt.final_price, 1000.0)
        self.loyalty_mock.redeem_points.assert_not_called()
        print("  -> При 0 баллов redeem_points не вызывался (OK)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
