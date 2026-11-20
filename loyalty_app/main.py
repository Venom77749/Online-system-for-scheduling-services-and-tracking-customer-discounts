import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
from cached_rules_proxy import DatabaseRulesProvider, CachedRulesProxy
from pricing_strategy import TierAccumulativeStrategy
from transaction_factory import AccrualTransactionCreator, RedemptionTransactionCreator
from loyalty_observer import LoyaltyAppointmentCompletedConsumer
from senders_adapter import VendorSmsSdk, SmsAdapter
from event_listener import NotificationAppointmentCompletedConsumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Loyalty & Notification Service (SQLite)", lifespan=lifespan)

# Инициализация паттернов (Proxy, Strategy, Factory, Adapter, Observer)
rules_proxy = CachedRulesProxy(DatabaseRulesProvider())
tier_strategy = TierAccumulativeStrategy(rules_provider=rules_proxy)
accrual_creator = AccrualTransactionCreator()
redemption_creator = RedemptionTransactionCreator()

loyalty_consumer = LoyaltyAppointmentCompletedConsumer(accrual_creator)
notification_consumer = NotificationAppointmentCompletedConsumer(SmsAdapter(VendorSmsSdk()))

# Подписчики на событие завершения записи (паттерн Observer)
event_subscribers = [
    loyalty_consumer.handle_event,
    notification_consumer.handle_event,
]


class DiscountRequest(BaseModel):
    client_id: str
    base_price: float


class RedeemRequest(BaseModel):
    client_id: str
    points: int
    appointment_id: str


class AppointmentCompletedEvent(BaseModel):
    appointment_id: str
    client_id: str
    final_price: float
    phone: str = "+7 (912) 888-77-66"


@app.get("/health")
def health():
    return {"service": "loyalty_app", "status": "ok"}


@app.get("/loyalty/rules")
def get_rules():
    return rules_proxy.fetch_rules()


@app.get("/loyalty/clients/{client_id}")
def get_client_profile(client_id: str):
    profile = db.get_or_create_client(client_id)
    transactions = db.get_client_transactions(client_id)
    rules = rules_proxy.fetch_rules()
    current_rule = max(
        [r for r in rules if profile["total_spent"] >= r["required_spend"]],
        key=lambda x: x["required_spend"],
    )
    return {
        "profile": {
            **profile,
            "tier": current_rule["tier"],
            "discount_percent": current_rule["discount_percent"],
        },
        "transactions": transactions,
    }


@app.get("/notifications")
def get_notifications():
    return db.list_notifications()


@app.post("/loyalty/calculate-discount")
def calculate_discount(req: DiscountRequest):
    client = db.get_or_create_client(req.client_id)
    discount = tier_strategy.calculate(
        base_price=req.base_price,
        total_spent=client["total_spent"],
    )
    return {
        "client_id": req.client_id,
        "total_spent": client["total_spent"],
        "discount_amount": discount,
    }


@app.post("/loyalty/redeem")
def redeem_points(req: RedeemRequest):
    client = db.get_or_create_client(req.client_id)
    try:
        tx = redemption_creator.create(
            client_id=req.client_id,
            points=req.points,
            current_balance=client["balance"],
            appointment_id=req.appointment_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.save_transaction(tx)
    db.update_client_loyalty(req.client_id, new_balance=tx.balance_after)
    return {
        "transaction_id": tx.id,
        "points_redeemed": abs(tx.points),
        "balance_after": tx.balance_after,
    }


@app.post("/events/appointment-completed")
def handle_appointment_completed(event: AppointmentCompletedEvent):
    payload = event.model_dump()
    for handler in event_subscribers:
        handler(payload)
    return {"status": "processed", "appointment_id": event.appointment_id}
