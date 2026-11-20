import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "loyalty.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discount_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier TEXT NOT NULL UNIQUE,
                required_spend REAL NOT NULL,
                discount_percent REAL NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO discount_rules (tier, required_spend, discount_percent) VALUES (?, ?, ?)",
            [
                ("Basic", 0.0, 0.0),
                ("Silver", 10000.0, 5.0),
                ("Gold", 30000.0, 10.0),
                ("Platinum", 60000.0, 15.0),
            ],
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_loyalty (
                client_id TEXT PRIMARY KEY,
                total_spent REAL NOT NULL DEFAULT 0.0,
                balance INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO client_loyalty (client_id, total_spent, balance) VALUES (?, ?, ?)",
            ("client-101", 35000.0, 400),
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bonus_transactions (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                appointment_id TEXT NULL,
                tx_type TEXT NOT NULL,
                points INTEGER NOT NULL,
                balance_before INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def fetch_discount_rules():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT tier, required_spend, discount_percent "
            "FROM discount_rules ORDER BY required_spend ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_or_create_client(client_id: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO client_loyalty (client_id, total_spent, balance) VALUES (?, 0.0, 0)",
            (client_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT client_id, total_spent, balance FROM client_loyalty WHERE client_id = ?",
            (client_id,),
        ).fetchone()
        return dict(row)


def update_client_loyalty(client_id: str, new_balance: int, add_spent: float = 0.0):
    with get_connection() as conn:
        conn.execute(
            "UPDATE client_loyalty SET balance = ?, total_spent = total_spent + ? WHERE client_id = ?",
            (new_balance, add_spent, client_id),
        )
        conn.commit()


def save_transaction(tx):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO bonus_transactions (
                id, client_id, appointment_id, tx_type, points, balance_before, balance_after
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.id,
                tx.client_id,
                tx.appointment_id,
                tx.tx_type,
                tx.points,
                tx.balance_before,
                tx.balance_after,
            ),
        )
        conn.commit()


def get_client_transactions(client_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM bonus_transactions WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]
