import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "booking.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                master_id TEXT NOT NULL,
                service_id TEXT NOT NULL,
                scheduled_datetime TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                base_price REAL NOT NULL,
                discount_amount REAL NOT NULL,
                points_redeemed INTEGER NOT NULL DEFAULT 0,
                final_price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'CREATED',
                phone TEXT NOT NULL DEFAULT '+7 (912) 888-77-66'
            )
            """
        )
        conn.commit()


def save_appointment(appointment, phone: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO appointments (
                id, client_id, master_id, service_id, scheduled_datetime,
                duration_minutes, base_price, discount_amount,
                points_redeemed, final_price, status, phone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                appointment.id,
                appointment.client_id,
                appointment.master_id,
                appointment.service_id,
                appointment.scheduled_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                appointment.duration_minutes,
                appointment.base_price,
                appointment.discount_amount,
                appointment.points_redeemed,
                appointment.final_price,
                appointment.status,
                phone,
            ),
        )
        conn.commit()


def get_appointment(appointment_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
        return dict(row) if row else None


def list_appointments():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments ORDER BY scheduled_datetime DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_appointment_status(appointment_id: str, status: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (status, appointment_id),
        )
        conn.commit()
