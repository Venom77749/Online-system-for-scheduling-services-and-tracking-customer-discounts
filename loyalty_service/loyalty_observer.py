from loyalty_service.transaction_factory import AccrualTransactionCreator


class LoyaltyAppointmentCompletedConsumer:
    """Подписчик события appointment.completed в Loyalty Service."""
    def __init__(self, accrual_factory: AccrualTransactionCreator):
        self._factory = accrual_factory

    def handle_event(self, event_data: dict):
        client_id = event_data["client_id"]
        final_price = event_data["final_price"]
        appointment_id = event_data["appointment_id"]

        # Начисление 5% бонусов от оплаченной суммы
        earned_points = int(final_price * 0.05)
        tx = self._factory.create(
            client_id=client_id,
            points=earned_points,
            current_balance=400,
            appointment_id=appointment_id
        )
        print(f"  [Loyalty Event Consumer]: Начислено {tx.points} бонусов. Баланс клиента: {tx.balance_after}")