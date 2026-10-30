from notification_service.senders_adapter import IMessageSender


class NotificationAppointmentCompletedConsumer:
    """Подписчик события appointment.completed в Notification Service."""
    def __init__(self, sender: IMessageSender):
        self._sender = sender

    def handle_event(self, event_data: dict):
        phone = event_data.get("phone", "+79990001122")
        text = f"Услуга завершена! К оплате: {event_data['final_price']} ₽. Спасибо за визит!"
        self._sender.send(recipient=phone, message=text)