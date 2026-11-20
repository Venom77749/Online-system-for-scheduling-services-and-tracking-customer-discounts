import httpx
import sys
sys.stdout.reconfigure(encoding="utf-8")

BOOKING_URL = "http://127.0.0.1:8001"
LOYALTY_URL = "http://127.0.0.1:8002"


def main():
    print("=== ЭТАП 1: Создание записи через Booking Service (:8001) ===")
    payload = {
        "appointment_id": "APT-2026-001",
        "client_id": "client-101",
        "master_id": "master-05",
        "service_id": "service-10",
        "dt": "2026-11-25T14:00:00",
        "base_price": 3000.0,
        "duration": 60,
        "points_to_redeem": 400,
        "phone": "+7 (912) 888-77-66",
    }
    resp = httpx.post(f"{BOOKING_URL}/appointments", json=payload, timeout=10.0)
    resp.raise_for_status()
    apt = resp.json()
    print(
        f"Запись сохранена в SQLite (booking.db): базовый прайс = {apt['base_price']} ₽, "
        f"скидка = {apt['discount_amount']} ₽, "
        f"списано бонусов = {apt['points_redeemed']}, "
        f"итоговый чек = {apt['final_price']} ₽"
    )

    print("\n=== ЭТАП 2: Подтверждение записи (State) ===")
    resp = httpx.post(f"{BOOKING_URL}/appointments/APT-2026-001/confirm", timeout=10.0)
    resp.raise_for_status()
    print("Ответ:", resp.json())

    print("\n=== ЭТАП 3: Завершение записи -> начисление 5% бонусов + SMS ===")
    resp = httpx.post(f"{BOOKING_URL}/appointments/APT-2026-001/complete", timeout=10.0)
    resp.raise_for_status()
    print("Ответ:", resp.json())

    print("\n=== ЭТАП 4: Проверка профиля клиента в Loyalty Service (:8002) ===")
    resp = httpx.get(f"{LOYALTY_URL}/loyalty/clients/client-101", timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    print("Профиль в SQLite (loyalty.db):", data["profile"])
    print("Количество транзакций:", len(data["transactions"]))


if __name__ == "__main__":
    main()
