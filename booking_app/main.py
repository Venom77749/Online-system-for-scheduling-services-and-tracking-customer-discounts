from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

import db
from booking_facade import BookingOrchestrationFacade
from appointment_state import AppointmentLifecycle
from clients import HttpLoyaltyClient, HttpEventBus


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Booking Service (SQLite)", lifespan=lifespan)

loyalty_client = HttpLoyaltyClient()
event_bus = HttpEventBus()
facade = BookingOrchestrationFacade(loyalty_client, event_bus)


class CreateAppointmentRequest(BaseModel):
    appointment_id: str
    client_id: str
    master_id: str
    service_id: str
    dt: datetime
    base_price: float
    duration: int = 60
    points_to_redeem: int = 0
    phone: str = "+7 (912) 888-77-66"


@app.get("/appointments")
def get_all_appointments():
    return db.list_appointments()


@app.get("/appointments/{appointment_id}")
def get_one_appointment(appointment_id: str):
    row = db.get_appointment(appointment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return row


@app.post("/appointments")
def create_appointment(req: CreateAppointmentRequest):
    try:
        appointment = facade.create_and_book(
            appointment_id=req.appointment_id,
            client_id=req.client_id,
            master_id=req.master_id,
            service_id=req.service_id,
            dt=req.dt,
            base_price=req.base_price,
            duration=req.duration,
            points_to_redeem=req.points_to_redeem,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Ошибка Loyalty Service: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Loyalty Service недоступен: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.save_appointment(appointment, phone=req.phone)
    return db.get_appointment(appointment.id)


@app.post("/appointments/{appointment_id}/confirm")
def confirm_appointment(appointment_id: str):
    row = db.get_appointment(appointment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    lifecycle = AppointmentLifecycle(appointment_id, initial_status=row["status"])
    try:
        lifecycle.confirm()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.update_appointment_status(appointment_id, lifecycle.status_name)
    return {"appointment_id": appointment_id, "status": lifecycle.status_name}


@app.post("/appointments/{appointment_id}/complete")
def complete_appointment(appointment_id: str):
    row = db.get_appointment(appointment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    def on_complete_callback(apt_id: str):
        event_bus.publish(
            "appointment.completed",
            {
                "appointment_id": apt_id,
                "client_id": row["client_id"],
                "final_price": float(row["final_price"]),
                "phone": row["phone"],
            },
        )

    lifecycle = AppointmentLifecycle(
        appointment_id,
        initial_status=row["status"],
        on_completed_callback=on_complete_callback,
    )
    try:
        lifecycle.complete()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Loyalty Service недоступен: {e}")

    db.update_appointment_status(appointment_id, lifecycle.status_name)
    return {"appointment_id": appointment_id, "status": lifecycle.status_name}


@app.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str):
    row = db.get_appointment(appointment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    lifecycle = AppointmentLifecycle(appointment_id, initial_status=row["status"])
    try:
        lifecycle.cancel()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.update_appointment_status(appointment_id, lifecycle.status_name)
    return {"appointment_id": appointment_id, "status": lifecycle.status_name}
