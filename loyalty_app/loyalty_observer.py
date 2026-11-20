import db
from transaction_factory import AccrualTransactionCreator


class LoyaltyAppointmentCompletedConsumer:
    """Подписчик события appointment.completed в Loyalty Service."""

    def __init__(self, accrual_factory: AccrualTransactionCreator):
        self._factory = accrual_factory

    def handle_event(self, event_data: dict):
        client_id = event_data["client_id"]
        final_price = float(event_data["final_price"])
        appointment_id = event_data["appointment_id"]

        client = db.get_or_create_client(client_id)
        current_balance = client["balance"]

        # Начисление 5% бонусов от оплаченной суммы
        earned_points = int(final_price * 0.05)
        tx = self._factory.create(
            client_id=client_id,
            points=earned_points,
            current_balance=current_balance,
            appointment_id=appointment_id,
        )
        db.save_transaction(tx)
        db.update_client_loyalty(client_id, new_balance=tx.balance_after, add_spent=final_price)
        print(
            f"  [Loyalty Event Consumer]: Начислено {tx.points} бонусов. "
            f"Баланс клиента {client_id}: {tx.balance_after}"
        )
