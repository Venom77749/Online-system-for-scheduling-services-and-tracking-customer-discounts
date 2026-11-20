import os
import sys
import time
import uuid
import subprocess
import threading
from datetime import datetime, timedelta
import httpx
import customtkinter as ctk
from tkinter import messagebox

BOOKING_URL = "http://127.0.0.1:8001"
LOYALTY_URL = "http://127.0.0.1:8002"

SERVICES = {
    "Стрижка (service-10) — 3000 руб.": ("service-10", 3000.0, 60),
    "Окрашивание (service-11) — 5500 руб.": ("service-11", 5500.0, 120),
    "Укладка (service-12) — 1800 руб.": ("service-12", 1800.0, 45),
    "Маникюр (service-13) — 2500 руб.": ("service-13", 2500.0, 90),
    "Комплексный уход (service-14) — 4200 руб.": ("service-14", 4200.0, 90),
}

MASTERS = [
    "master-01 (Анна)",
    "master-03 (Дмитрий)",
    "master-05 (Елена)",
    "master-07 (Максим)",
]

STATUS_STYLES = {
    "CREATED": ("#3B82F6", "Создана"),
    "CONFIRMED": ("#F59E0B", "Подтверждена"),
    "COMPLETED": ("#10B981", "Завершена"),
    "CANCELLED": ("#EF4444", "Отменена"),
}

TIER_COLORS = {
    "Basic": "#64748B",
    "Silver": "#94A3B8",
    "Gold": "#EAB308",
    "Platinum": "#A855F7",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ServiceManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Система записи на услуги и учета скидок (2 микросервиса + SQLite)")
        self.geometry("1220x760")
        self.minsize(1060, 680)

        self._processes: list[subprocess.Popen] = []
        self._client_profile: dict = {}
        self._rules: list[dict] = []

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Первичная проверка сервисов и загрузка данных
        self.after(200, self.refresh_all)

    # ---------------- UI LAYOUT ----------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- TOP BAR ---
        top_bar = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=("#E2E8F0", "#0F172A"))
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        top_bar.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            top_bar,
            text="Booking & Loyalty Microservices",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title_lbl.grid(row=0, column=0, padx=18, pady=12, sticky="w")

        status_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=10, sticky="e")

        self.booking_badge = ctk.CTkLabel(
            status_frame,
            text="  Booking :8001 — Offline  ",
            fg_color="#7F1D1D",
            text_color="#FCA5A5",
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.booking_badge.pack(side="left", padx=6)

        self.loyalty_badge = ctk.CTkLabel(
            status_frame,
            text="  Loyalty :8002 — Offline  ",
            fg_color="#7F1D1D",
            text_color="#FCA5A5",
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.loyalty_badge.pack(side="left", padx=6)

        self.start_services_btn = ctk.CTkButton(
            top_bar,
            text="Запустить сервисы",
            width=150,
            fg_color="#16A34A",
            hover_color="#15803D",
            command=self.start_microservices,
        )
        self.start_services_btn.grid(row=0, column=2, padx=(6, 8), pady=10)

        refresh_btn = ctk.CTkButton(
            top_bar,
            text="Обновить",
            width=100,
            command=self.refresh_all,
        )
        refresh_btn.grid(row=0, column=3, padx=(0, 16), pady=10)

        # --- LEFT PANEL: CREATE APPOINTMENT ---
        left_panel = ctk.CTkFrame(self, corner_radius=12)
        left_panel.grid(row=1, column=0, padx=(16, 8), pady=16, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_panel,
            text="Новая запись (Facade + Builder)",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 10), sticky="w")

        # Client ID row
        ctk.CTkLabel(left_panel, text="ID клиента:", anchor="w").grid(
            row=1, column=0, padx=16, pady=(4, 0), sticky="w"
        )
        client_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        client_row.grid(row=2, column=0, padx=16, pady=(2, 8), sticky="ew")
        client_row.grid_columnconfigure(0, weight=1)

        self.client_entry = ctk.CTkEntry(client_row, placeholder_text="client-101")
        self.client_entry.insert(0, "client-101")
        self.client_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            client_row,
            text="Профиль",
            width=85,
            command=self.refresh_all,
        ).grid(row=0, column=1)

        # Mini client info banner
        self.client_hint_lbl = ctk.CTkLabel(
            left_panel,
            text="Уровень: — | Скидка: — | Баланс: —",
            font=ctk.CTkFont(size=12),
            text_color="#93C5FD",
            fg_color=("#DBEAFE", "#1E293B"),
            corner_radius=8,
            height=32,
        )
        self.client_hint_lbl.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        # Service
        ctk.CTkLabel(left_panel, text="Услуга:", anchor="w").grid(
            row=4, column=0, padx=16, pady=(2, 0), sticky="w"
        )
        self.service_var = ctk.StringVar(value=list(SERVICES.keys())[0])
        self.service_menu = ctk.CTkOptionMenu(
            left_panel,
            values=list(SERVICES.keys()),
            variable=self.service_var,
            command=self._on_service_change,
        )
        self.service_menu.grid(row=5, column=0, padx=16, pady=(2, 8), sticky="ew")

        # Master
        ctk.CTkLabel(left_panel, text="Мастер:", anchor="w").grid(
            row=6, column=0, padx=16, pady=(2, 0), sticky="w"
        )
        self.master_var = ctk.StringVar(value=MASTERS[2])
        self.master_menu = ctk.CTkOptionMenu(
            left_panel, values=MASTERS, variable=self.master_var
        )
        self.master_menu.grid(row=7, column=0, padx=16, pady=(2, 8), sticky="ew")

        # Price & Duration
        pd_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        pd_row.grid(row=8, column=0, padx=16, pady=(2, 8), sticky="ew")
        pd_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(pd_row, text="Цена (руб.):", anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(pd_row, text="Длит. (мин):", anchor="w").grid(row=0, column=1, padx=(8, 0), sticky="w")

        self.price_entry = ctk.CTkEntry(pd_row)
        self.price_entry.insert(0, "3000")
        self.price_entry.grid(row=1, column=0, sticky="ew")
        self.price_entry.bind("<KeyRelease>", lambda _e: self._update_price_preview())

        self.duration_entry = ctk.CTkEntry(pd_row)
        self.duration_entry.insert(0, "60")
        self.duration_entry.grid(row=1, column=1, padx=(8, 0), sticky="ew")

        # Date & Phone
        ctk.CTkLabel(left_panel, text="Дата и время (YYYY-MM-DD HH:MM):", anchor="w").grid(
            row=9, column=0, padx=16, pady=(2, 0), sticky="w"
        )
        default_dt = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0)
        self.dt_entry = ctk.CTkEntry(left_panel)
        self.dt_entry.insert(0, default_dt.strftime("%Y-%m-%d %H:%M"))
        self.dt_entry.grid(row=10, column=0, padx=16, pady=(2, 8), sticky="ew")

        ctk.CTkLabel(left_panel, text="Телефон для SMS:", anchor="w").grid(
            row=11, column=0, padx=16, pady=(2, 0), sticky="w"
        )
        self.phone_entry = ctk.CTkEntry(left_panel)
        self.phone_entry.insert(0, "+7 (912) 888-77-66")
        self.phone_entry.grid(row=12, column=0, padx=16, pady=(2, 8), sticky="ew")

        # Points to redeem
        ctk.CTkLabel(left_panel, text="Списать бонусов (макс. 50% чека):", anchor="w").grid(
            row=13, column=0, padx=16, pady=(2, 0), sticky="w"
        )
        self.points_entry = ctk.CTkEntry(left_panel)
        self.points_entry.insert(0, "0")
        self.points_entry.grid(row=14, column=0, padx=16, pady=(2, 10), sticky="ew")
        self.points_entry.bind("<KeyRelease>", lambda _e: self._update_price_preview())

        # Price preview box
        self.preview_lbl = ctk.CTkLabel(
            left_panel,
            text="Предварительный итог: —",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#E2E8F0", "#1E293B"),
            corner_radius=8,
            height=42,
        )
        self.preview_lbl.grid(row=15, column=0, padx=16, pady=(2, 12), sticky="ew")

        # Submit button
        self.create_btn = ctk.CTkButton(
            left_panel,
            text="Создать запись",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.create_appointment,
        )
        self.create_btn.grid(row=16, column=0, padx=16, pady=(0, 12), sticky="ew")

        # Status bar inside left panel
        self.toast_lbl = ctk.CTkLabel(
            left_panel,
            text="",
            font=ctk.CTkFont(size=12),
            wraplength=340,
            justify="left",
        )
        self.toast_lbl.grid(row=17, column=0, padx=16, pady=(0, 12), sticky="ew")

        # --- RIGHT PANEL: TABS ---
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.grid(row=1, column=1, padx=(8, 16), pady=16, sticky="nsew")

        self.tab_appointments = self.tabview.add("Записи (Booking)")
        self.tab_loyalty = self.tabview.add("Лояльность и бонусы (Loyalty)")
        self.tab_notifications = self.tabview.add("SMS-уведомления (Observer)")

        # Tab 1: Appointments scrollable list
        self.tab_appointments.grid_columnconfigure(0, weight=1)
        self.tab_appointments.grid_rowconfigure(0, weight=1)
        self.appointments_scroll = ctk.CTkScrollableFrame(self.tab_appointments, fg_color="transparent")
        self.appointments_scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.appointments_scroll.grid_columnconfigure(0, weight=1)

        # Tab 2: Loyalty profile + transactions
        self.tab_loyalty.grid_columnconfigure(0, weight=1)
        self.tab_loyalty.grid_rowconfigure(2, weight=1)

        self.loyalty_card = ctk.CTkFrame(self.tab_loyalty, corner_radius=12, fg_color=("#E2E8F0", "#1E293B"))
        self.loyalty_card.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 12))
        self.loyalty_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.tier_lbl = ctk.CTkLabel(
            self.loyalty_card, text="Уровень: —", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.tier_lbl.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.spent_lbl = ctk.CTkLabel(
            self.loyalty_card, text="Накоплено трат: —", font=ctk.CTkFont(size=14)
        )
        self.spent_lbl.grid(row=0, column=1, padx=16, pady=(14, 4))

        self.balance_lbl = ctk.CTkLabel(
            self.loyalty_card,
            text="Бонусы: —",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#34D399",
        )
        self.balance_lbl.grid(row=0, column=2, padx=16, pady=(14, 4), sticky="e")

        self.tier_progress = ctk.CTkProgressBar(self.loyalty_card)
        self.tier_progress.set(0)
        self.tier_progress.grid(row=1, column=0, columnspan=3, padx=16, pady=(6, 4), sticky="ew")

        self.next_tier_lbl = ctk.CTkLabel(
            self.loyalty_card, text="", font=ctk.CTkFont(size=12), text_color="#94A3B8"
        )
        self.next_tier_lbl.grid(row=2, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(
            self.tab_loyalty,
            text="История бонусных транзакций (Factory Method)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")

        self.tx_scroll = ctk.CTkScrollableFrame(self.tab_loyalty, fg_color="transparent")
        self.tx_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        self.tx_scroll.grid_columnconfigure(0, weight=1)

        # Tab 3: Notifications log
        self.tab_notifications.grid_columnconfigure(0, weight=1)
        self.tab_notifications.grid_rowconfigure(0, weight=1)
        self.notif_scroll = ctk.CTkScrollableFrame(self.tab_notifications, fg_color="transparent")
        self.notif_scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.notif_scroll.grid_columnconfigure(0, weight=1)

    # ---------------- MICROSERVICES LAUNCHER ----------------

    def start_microservices(self):
        self.start_services_btn.configure(state="disabled", text="Запуск...")
        threading.Thread(target=self._spawn_services_thread, daemon=True).start()

    def _spawn_services_thread(self):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        services = [
            ("loyalty_app", 8002, f"{LOYALTY_URL}/health"),
            ("booking_app", 8001, f"{BOOKING_URL}/health"),
        ]

        for folder, port, health_url in services:
            try:
                httpx.get(health_url, timeout=1.0)
                continue  # уже запущен
            except Exception:
                pass

            cwd = os.path.join(root_dir, folder)
            proc = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-m", "uvicorn", "main:app", "--port", str(port)],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            self._processes.append(proc)

        # Ждем поднятия серверов до 6 секунд
        for _ in range(12):
            ok_b = self._ping(f"{BOOKING_URL}/health")
            ok_l = self._ping(f"{LOYALTY_URL}/health")
            if ok_b and ok_l:
                break
            time.sleep(0.5)

        self.after(0, lambda: self.start_services_btn.configure(state="normal", text="Запустить сервисы"))
        self.after(0, lambda: self._set_toast("Микросервисы запущены!", "#34D399"))
        self.after(0, self.refresh_all)

    def _on_close(self):
        for p in self._processes:
            try:
                p.terminate()
            except Exception:
                pass
        self.destroy()

    # ---------------- HELPERS ----------------

    @staticmethod
    def _ping(url: str) -> bool:
        try:
            r = httpx.get(url, timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    def _set_toast(self, text: str, color: str = "#93C5FD"):
        self.toast_lbl.configure(text=text, text_color=color)

    def _on_service_change(self, choice: str):
        _, price, duration = SERVICES[choice]
        self.price_entry.delete(0, "end")
        self.price_entry.insert(0, str(int(price)))
        self.duration_entry.delete(0, "end")
        self.duration_entry.insert(0, str(duration))
        self._update_price_preview()

    def _update_price_preview(self):
        try:
            base = float(self.price_entry.get().strip() or 0)
            pts = int(self.points_entry.get().strip() or 0)
        except ValueError:
            self.preview_lbl.configure(text="Введите корректные числа")
            return

        disc_pct = float(self._client_profile.get("discount_percent", 0.0))
        disc = round(base * (disc_pct / 100.0), 2)
        after_disc = max(0.0, base - disc)
        max_pts = int(after_disc * 0.5)
        used_pts = min(max(0, pts), max_pts)
        final = round(after_disc - used_pts, 2)
        self.preview_lbl.configure(
            text=f"Скидка ({disc_pct:.0f}%): -{disc:.0f} | Баллы: -{used_pts} | Итого: {final:.0f} руб."
        )

    # ---------------- DATA LOADING ----------------

    def refresh_all(self):
        client_id = self.client_entry.get().strip() or "client-101"
        threading.Thread(target=self._fetch_all_thread, args=(client_id,), daemon=True).start()

    def _fetch_all_thread(self, client_id: str):
        booking_ok = self._ping(f"{BOOKING_URL}/health")
        loyalty_ok = self._ping(f"{LOYALTY_URL}/health")

        appointments = []
        client_data = None
        rules = []
        notifications = []

        if booking_ok:
            try:
                r = httpx.get(f"{BOOKING_URL}/appointments", timeout=3.0)
                if r.status_code == 200:
                    appointments = r.json()
            except Exception:
                pass

        if loyalty_ok:
            try:
                r = httpx.get(f"{LOYALTY_URL}/loyalty/clients/{client_id}", timeout=3.0)
                if r.status_code == 200:
                    client_data = r.json()
                r2 = httpx.get(f"{LOYALTY_URL}/loyalty/rules", timeout=3.0)
                if r2.status_code == 200:
                    rules = r2.json()
                r3 = httpx.get(f"{LOYALTY_URL}/notifications", timeout=3.0)
                if r3.status_code == 200:
                    notifications = r3.json()
            except Exception:
                pass

        self.after(
            0,
            lambda: self._apply_loaded_data(
                booking_ok, loyalty_ok, appointments, client_data, rules, notifications
            ),
        )

    def _apply_loaded_data(self, booking_ok, loyalty_ok, appointments, client_data, rules, notifications):
        if booking_ok:
            self.booking_badge.configure(
                text="  Booking :8001 — Online  ", fg_color="#14532D", text_color="#86EFAC"
            )
        else:
            self.booking_badge.configure(
                text="  Booking :8001 — Offline  ", fg_color="#7F1D1D", text_color="#FCA5A5"
            )

        if loyalty_ok:
            self.loyalty_badge.configure(
                text="  Loyalty :8002 — Online  ", fg_color="#14532D", text_color="#86EFAC"
            )
        else:
            self.loyalty_badge.configure(
                text="  Loyalty :8002 — Offline  ", fg_color="#7F1D1D", text_color="#FCA5A5"
            )

        self._rules = rules
        if client_data:
            self._client_profile = client_data["profile"]
            self._render_loyalty(client_data["profile"], client_data["transactions"])
        else:
            self.client_hint_lbl.configure(text="Loyalty Service недоступен — нажмите «Запустить сервисы»")

        self._render_appointments(appointments)
        self._render_notifications(notifications)
        self._update_price_preview()

    # ---------------- RENDERERS ----------------

    def _render_loyalty(self, profile: dict, transactions: list):
        tier = profile.get("tier", "Basic")
        disc = profile.get("discount_percent", 0.0)
        spent = float(profile.get("total_spent", 0.0))
        bal = int(profile.get("balance", 0))

        self.client_hint_lbl.configure(
            text=f"Уровень: {tier} ({disc:.0f}%)  |  Баланс: {bal} балл."
        )

        self.tier_lbl.configure(
            text=f"Уровень: {tier} ({disc:.0f}%)",
            text_color=TIER_COLORS.get(tier, "#E2E8F0"),
        )
        self.spent_lbl.configure(text=f"Накоплено трат: {spent:,.0f} руб.".replace(",", " "))
        self.balance_lbl.configure(text=f"Бонусы: {bal}")

        # Прогресс до следующего уровня
        next_rules = [r for r in self._rules if r["required_spend"] > spent]
        if next_rules:
            nxt = next_rules[0]
            ratio = min(1.0, spent / nxt["required_spend"]) if nxt["required_spend"] > 0 else 1.0
            left = nxt["required_spend"] - spent
            self.tier_progress.set(ratio)
            self.next_tier_lbl.configure(
                text=f"До уровня {nxt['tier']} ({nxt['discount_percent']:.0f}%) осталось {left:,.0f} руб.".replace(",", " ")
            )
        else:
            self.tier_progress.set(1.0)
            self.next_tier_lbl.configure(text="Достигнут максимальный уровень Platinum!")

        for w in self.tx_scroll.winfo_children():
            w.destroy()

        if not transactions:
            ctk.CTkLabel(
                self.tx_scroll, text="Транзакций пока нет", text_color="#94A3B8"
            ).grid(row=0, column=0, pady=20)
            return

        for idx, tx in enumerate(transactions):
            row_card = ctk.CTkFrame(self.tx_scroll, corner_radius=8, fg_color=("#F1F5F9", "#1E293B"))
            row_card.grid(row=idx, column=0, sticky="ew", pady=4, padx=4)
            row_card.grid_columnconfigure(1, weight=1)

            is_accrual = tx["tx_type"] == "ACCRUAL"
            color = "#10B981" if is_accrual else "#F97316"
            sign = "+" if tx["points"] > 0 else ""

            ctk.CTkLabel(
                row_card,
                text=f" {tx['tx_type']} ",
                fg_color=color,
                text_color="#FFFFFF",
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=105,
            ).grid(row=0, column=0, padx=10, pady=10)

            info = f"Запись: {tx.get('appointment_id') or '—'}   |   Баланс: {tx['balance_before']} -> {tx['balance_after']}"
            ctk.CTkLabel(row_card, text=info, anchor="w").grid(row=0, column=1, padx=8, sticky="w")

            ctk.CTkLabel(
                row_card,
                text=f"{sign}{tx['points']} балл.",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=color,
            ).grid(row=0, column=2, padx=14)

    def _render_appointments(self, appointments: list):
        for w in self.appointments_scroll.winfo_children():
            w.destroy()

        if not appointments:
            ctk.CTkLabel(
                self.appointments_scroll,
                text="Записей пока нет. Создайте первую запись в панели слева.",
                text_color="#94A3B8",
            ).grid(row=0, column=0, pady=30)
            return

        for idx, apt in enumerate(appointments):
            card = ctk.CTkFrame(self.appointments_scroll, corner_radius=10, fg_color=("#F1F5F9", "#1E293B"))
            card.grid(row=idx, column=0, sticky="ew", pady=6, padx=4)
            card.grid_columnconfigure(0, weight=1)

            status = apt["status"]
            st_color, st_text = STATUS_STYLES.get(status, ("#64748B", status))

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
            header.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                header,
                text=f"{apt['id']}  •  Клиент: {apt['client_id']}  •  {apt['scheduled_datetime']}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                header,
                text=f"  {st_text} ({status})  ",
                fg_color=st_color,
                text_color="#FFFFFF",
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=1, sticky="e")

            details_text = (
                f"Услуга: {apt['service_id']}   |   Мастер: {apt['master_id']}   |   "
                f"База: {apt['base_price']:.0f} руб.   |   Скидка: -{apt['discount_amount']:.0f} руб.   |   "
                f"Баллы: -{apt['points_redeemed']}   |   Итого: {apt['final_price']:.0f} руб."
            )
            ctk.CTkLabel(
                card, text=details_text, font=ctk.CTkFont(size=12), text_color="#CBD5E1", anchor="w"
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

            apt_id = apt["id"]
            ctk.CTkButton(
                btn_row,
                text="Подтвердить",
                width=115,
                height=30,
                fg_color="#D97706",
                hover_color="#B45309",
                command=lambda i=apt_id: self.change_status(i, "confirm"),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_row,
                text="Завершить (+5% + SMS)",
                width=165,
                height=30,
                fg_color="#059669",
                hover_color="#047857",
                command=lambda i=apt_id: self.change_status(i, "complete"),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_row,
                text="Отменить",
                width=100,
                height=30,
                fg_color="#DC2626",
                hover_color="#B91C1C",
                command=lambda i=apt_id: self.change_status(i, "cancel"),
            ).pack(side="left")

    def _render_notifications(self, notifications: list):
        for w in self.notif_scroll.winfo_children():
            w.destroy()

        if not notifications:
            ctk.CTkLabel(
                self.notif_scroll,
                text="SMS-уведомлений пока нет. Завершите любую подтвержденную запись, чтобы сработал Observer + SmsAdapter.",
                text_color="#94A3B8",
                wraplength=600,
            ).grid(row=0, column=0, pady=30)
            return

        for idx, n in enumerate(notifications):
            card = ctk.CTkFrame(self.notif_scroll, corner_radius=8, fg_color=("#F1F5F9", "#1E293B"))
            card.grid(row=idx, column=0, sticky="ew", pady=4, padx=4)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=f"SMS на {n['recipient']}  •  {n['created_at']}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#60A5FA",
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

            ctk.CTkLabel(
                card, text=n["message"], anchor="w", wraplength=680, justify="left"
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

    # ---------------- ACTIONS ----------------

    def create_appointment(self):
        client_id = self.client_entry.get().strip() or "client-101"
        service_id = SERVICES[self.service_var.get()][0]
        master_id = self.master_var.get().split(" ")[0]
        phone = self.phone_entry.get().strip() or "+7 (912) 888-77-66"

        try:
            base_price = float(self.price_entry.get().strip())
            duration = int(self.duration_entry.get().strip())
            points = int(self.points_entry.get().strip() or 0)
            dt_obj = datetime.strptime(self.dt_entry.get().strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Проверьте цену, длительность, баллы и формат даты (YYYY-MM-DD HH:MM).")
            return

        apt_id = f"APT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        payload = {
            "appointment_id": apt_id,
            "client_id": client_id,
            "master_id": master_id,
            "service_id": service_id,
            "dt": dt_obj.isoformat(),
            "base_price": base_price,
            "duration": duration,
            "points_to_redeem": points,
            "phone": phone,
        }

        def worker():
            try:
                r = httpx.post(f"{BOOKING_URL}/appointments", json=payload, timeout=8.0)
                if r.status_code != 200:
                    detail = r.json().get("detail", r.text)
                    self.after(0, lambda: messagebox.showerror("Ошибка Booking Service", str(detail)))
                    return
                apt = r.json()
                self.after(
                    0,
                    lambda: self._set_toast(
                        f"Запись {apt['id']} создана! Итого: {apt['final_price']:.0f} руб.", "#34D399"
                    ),
                )
                self.after(0, self.refresh_all)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Сервис недоступен", f"Не удалось подключиться к Booking Service:\n{e}"))

        threading.Thread(target=worker, daemon=True).start()

    def change_status(self, appointment_id: str, action: str):
        def worker():
            try:
                r = httpx.post(f"{BOOKING_URL}/appointments/{appointment_id}/{action}", timeout=8.0)
                if r.status_code != 200:
                    detail = r.json().get("detail", r.text)
                    self.after(0, lambda: messagebox.showwarning("Паттерн State запретил переход", str(detail)))
                    return
                data = r.json()
                msg = f"Запись {appointment_id} -> {data['status']}"
                if action == "complete":
                    msg += " (начислен кэшбэк 5% и отправлена SMS)"
                self.after(0, lambda: self._set_toast(msg, "#34D399"))
                self.after(0, self.refresh_all)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Ошибка сети", str(e)))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = ServiceManagerApp()
    app.mainloop()
