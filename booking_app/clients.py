import os
import httpx

LOYALTY_SERVICE_URL = os.getenv("LOYALTY_SERVICE_URL", "http://127.0.0.1:8002")


class HttpLoyaltyClient:
    def calculate_discount(self, client_id: str, base_price: float) -> dict:
        response = httpx.post(
            f"{LOYALTY_SERVICE_URL}/loyalty/calculate-discount",
            json={"client_id": client_id, "base_price": base_price},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()

    def redeem_points(self, client_id: str, points: int, appointment_id: str) -> dict:
        response = httpx.post(
            f"{LOYALTY_SERVICE_URL}/loyalty/redeem",
            json={
                "client_id": client_id,
                "points": points,
                "appointment_id": appointment_id,
            },
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()


class HttpEventBus:
    def publish(self, topic: str, payload: dict):
        print(f"[Booking HTTP Bus] Событие '{topic}': {payload}")
        if topic == "appointment.completed":
            response = httpx.post(
                f"{LOYALTY_SERVICE_URL}/events/appointment-completed",
                json=payload,
                timeout=5.0,
            )
            response.raise_for_status()
