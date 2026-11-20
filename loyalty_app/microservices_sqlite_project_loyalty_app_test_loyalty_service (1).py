import os
import sys
import unittest
from unittest.mock import MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Добавляем папку loyalty_app в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cached_rules_proxy import CachedRulesProxy
from pricing_strategy import TierAccumulativeStrategy, FixedPromoStrategy
from transaction_factory import AccrualTransactionCreator, RedemptionTransactionCreator
from loyalty_observer import LoyaltyAppointmentCompletedConsumer
from senders_adapter import SmsAdapter
from event_listener import NotificationAppointmentCompletedConsumer


class TestPricingStrategyAndProxy(unittest.TestCase):
    """Unit-тесты для паттернов Proxy и Strategy."""

    def setUp(self):
        self.sample_rules = [
            {"tier": "Basic", "required_spend": 0.0, "discount_percent": 0.0},
            {"tier": "Silver", "required_spend": 10000.0, "discount_percent": 5.0},
            {"tier": "Gold", "required_spend": 30000.0, "discount_percent": 10.0},
            {"tier": "Platinum", "required_spend": 60000.0, "discount_percent": 15.0},
        ]
        self.db_provider_mock = MagicMock()
        self.db_provider_mock.fetch_rules.return_value = self.sample_rules
        self.proxy = CachedRulesProxy(self.db_provider_mock)
        self.strategy = TierAccumulativeStrategy(self.proxy)

    def test_tier_strategy_gold_level_returns_10_percent(self):
        """[Положительный] Уровень Gold (35 000 руб.) дает скидку 10%"""
        discount = self.strategy.calculate(base_price=3000.0, total_spent=35000.0)
        self.assertEqual(discount, 300.0)
        print(f"  -> Скидка для Gold от 3000 руб. = {discount} руб.")

    def test_tier_strategy_exact_boundary_silver(self):
        """[Граница] Порог Silver: 9999 руб. -> 0%, ровно 10000 руб. -> 5%"""
        d_below = self.strategy.calculate(base_price=1000.0, total_spent=9999.0)
        d_exact = self.strategy.calculate(base_price=1000.0, total_spent=10000.0)
        self.assertEqual(d_below, 0.0)
        self.assertEqual(d_exact, 50.0)
        print(f"  -> При 9999 руб. скидка={d_below}, при 10000 руб. скидка={d_exact}")

    def test_tier_strategy_zero_price_and_zero_spent(self):
        """[Граница] Нулевая цена и 0 трат дают скидку 0"""
        discount = self.strategy.calculate(base_price=0.0, total_spent=0.0)
        self.assertEqual(discount, 0.0)
        print(f"  -> База=0, траты=0 -> скидка={discount}")

    def test_cached_rules_proxy_queries_db_only_once(self):
        """[Положительный / Mock] Прокси обращается к БД только 1 раз при 3 вызовах"""
        self.proxy.fetch_rules()
        self.proxy.fetch_rules()
        self.proxy.fetch_rules()
        self.db_provider_mock.fetch_rules.assert_called_once()
        print("  -> Вызовов fetch_rules: 3, обращений к БД: 1 (кэш работает)")

    def test_tier_strategy_empty_rules_raises_value_error(self):
        """[Пустота / Исключение] Пустой список правил скидок вызывает ValueError"""
        self.db_provider_mock.fetch_rules.return_value = []
        self.proxy.clear()
        with self.assertRaises(ValueError):
            self.strategy.calculate(base_price=1000.0, total_spent=5000.0)
        print("  -> Поймано ожидаемое исключение ValueError при пустых правилах")

    def test_fixed_promo_strategy_calculates_percent(self):
        """[Положительный] Фиксированная промо-скидка 20%"""
        promo = FixedPromoStrategy(percent=20.0)
        discount = promo.calculate(base_price=2500.0, total_spent=0.0)
        self.assertEqual(discount, 500.0)
        print(f"  -> Промо-скидка 20% от 2500 руб. = {discount} руб.")


class TestTransactionFactory(unittest.TestCase):
    """Unit-тесты для паттерна Factory Method (начисление и списание баллов)."""

    def test_accrual_creator_increases_balance(self):
        """[Положительный] Начисление 150 баллов увеличивает баланс с 400 до 550"""
        creator = AccrualTransactionCreator()
        tx = creator.create(client_id="client-101", points=150, current_balance=400, appointment_id="APT-1")

        self.assertEqual(tx.tx_type, "ACCRUAL")
        self.assertEqual(tx.points, 150)
        self.assertEqual(tx.balance_before, 400)
        self.assertEqual(tx.balance_after, 550)
        print(f"  -> Транзакция {tx.tx_type}: {tx.balance_before} -> {tx.balance_after}")

    def test_redemption_creator_exact_balance_boundary(self):
        """[Граница] Списание ровно всего баланса (400 из 400) обнуляет счет"""
        creator = RedemptionTransactionCreator()
        tx = creator.create(client_id="client-101", points=400, current_balance=400)

        self.assertEqual(tx.tx_type, "REDEMPTION")
        self.assertEqual(tx.points, -400)
        self.assertEqual(tx.balance_after, 0)
        print(f"  -> Списано ровно 400 из 400, остаток={tx.balance_after}")

    def test_redemption_creator_insufficient_balance_raises_value_error(self):
        """[Исключение] Списание больше баланса (401 > 400) вызывает ValueError"""
        creator = RedemptionTransactionCreator()
        with self.assertRaises(ValueError) as ctx:
            creator.create(client_id="client-101", points=401, current_balance=400)
        print(f"  -> Поймано ожидаемое исключение: {ctx.exception}")


class TestObserversAndAdapter(unittest.TestCase):
    """Unit-тесты для паттернов Observer и Adapter с изоляцией БД и внешнего SDK."""

    @patch("loyalty_observer.db")
    def test_loyalty_observer_accrues_5_percent_cashback(self, mock_db):
        """[Положительный / Mock] Наблюдатель начисляет 5% кэшбэка от 2300 руб. (+115)"""
        mock_db.get_or_create_client.return_value = {"client_id": "client-101", "balance": 100}
        consumer = LoyaltyAppointmentCompletedConsumer(AccrualTransactionCreator())

        consumer.handle_event({
            "appointment_id": "APT-55",
            "client_id": "client-101",
            "final_price": 2300.0,
        })

        mock_db.save_transaction.assert_called_once()
        mock_db.update_client_loyalty.assert_called_once_with(
            "client-101", new_balance=215, add_spent=2300.0
        )
        print("  -> Кэшбэк 115 баллов начислен, новый баланс=215")

    def test_sms_adapter_returns_true_on_200_and_false_on_error(self):
        """[Положительный + Ошибка / Mock] Адаптер возвращает True при 200 и False при 500"""
        sdk_mock = MagicMock()
        adapter = SmsAdapter(sdk_mock)

        sdk_mock.send_sms_packet.return_value = 200
        self.assertTrue(adapter.send("+79991112233", "Привет"))

        sdk_mock.send_sms_packet.return_value = 500
        self.assertFalse(adapter.send("+79991112233", "Ошибка"))
        print("  -> Код 200 -> True, код 500 -> False")

    def test_notification_observer_uses_default_phone_when_missing(self):
        """[Пустота / Mock] При отсутствии телефона в событии берется номер по умолчанию"""
        sender_mock = MagicMock()
        consumer = NotificationAppointmentCompletedConsumer(sender_mock)

        consumer.handle_event({"final_price": 1500.0})

        sender_mock.send.assert_called_once()
        _, kwargs = sender_mock.send.call_args
        self.assertEqual(kwargs["recipient"], "+79990001122")
        self.assertIn("1500.0", kwargs["message"])
        print(f"  -> Использован номер по умолчанию: {kwargs['recipient']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
