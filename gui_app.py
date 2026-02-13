import tkinter as tk
from tkinter import messagebox
import threading
from config import Config, Colors
from models import User, Transaction
from database import UserDatabase, HistoryManager
from telegram_bot import TelegramBot


# ══════════════════════════════
#  ВИДЖЕТЫ
# ══════════════════════════════

class StyledEntry(tk.Entry):
    def __init__(self, parent, placeholder="", show_char=None, **kw):
        self._ph = placeholder
        self._show = show_char
        self._is_ph = False
        d = dict(bg=Colors.INPUT_BG, fg=Colors.TEXT,
                 insertbackground=Colors.TEXT,
                 font=("Arial", 13), relief="flat", bd=10,
                 highlightthickness=2, highlightcolor=Colors.ACCENT,
                 highlightbackground=Colors.BORDER)
        d.update(kw)
        super().__init__(parent, **d)
        if placeholder:
            self._show_ph()
            self.bind("<FocusIn>", self._fi)
            self.bind("<FocusOut>", self._fo)

    def _show_ph(self):
        self._is_ph = True
        self.configure(show="", fg=Colors.TEXT2)
        self.insert(0, self._ph)

    def _fi(self, e=None):
        if self._is_ph:
            self.delete(0, tk.END)
            self.configure(fg=Colors.TEXT)
            if self._show:
                self.configure(show=self._show)
            self._is_ph = False

    def _fo(self, e=None):
        if not self.get():
            self._show_ph()

    def val(self):
        return "" if self._is_ph else self.get().strip()


class StyledButton(tk.Button):
    def __init__(self, parent, text="", command=None,
                 color=None, hover=None, **kw):
        c = color or Colors.BTN
        h = hover or Colors.BTN_HOVER
        d = dict(bg=c, fg="white", font=("Arial", 13, "bold"),
                 relief="flat", cursor="hand2", bd=0,
                 activebackground=h, activeforeground="white", pady=12)
        d.update(kw)
        super().__init__(parent, text=text, command=command, **d)
        self.bind("<Enter>", lambda e: self.configure(bg=h))
        self.bind("<Leave>", lambda e: self.configure(bg=c))


class NavButton(tk.Button):
    def __init__(self, parent, text="", command=None, active=False, **kw):
        bg = Colors.NAV_ACTIVE if active else Colors.NAV_BG
        fg = Colors.TEXT if active else Colors.NAV_INACTIVE
        super().__init__(parent, text=text, command=command,
                         bg=bg, fg=fg, font=("Arial", 11, "bold"),
                         relief="flat", cursor="hand2", bd=0, pady=14,
                         activebackground=Colors.NAV_ACTIVE,
                         activeforeground=Colors.TEXT, **kw)

    def set_active(self, a):
        self.configure(
            bg=Colors.NAV_ACTIVE if a else Colors.NAV_BG,
            fg=Colors.TEXT if a else Colors.NAV_INACTIVE)


# ══════════════════════════════
#  БАЗОВЫЙ ЭКРАН
# ══════════════════════════════

class BaseScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=Colors.BG)
        self.app = app
        self._build()

    def _build(self):
        pass

    def _lbl(self, parent, text, size=12, bold=False,
             color=Colors.TEXT, bg=Colors.BG):
        w = "bold" if bold else "normal"
        return tk.Label(parent, text=text, bg=bg, fg=color,
                        font=("Arial", size, w))


# ══════════════════════════════
#  ВХОД
# ══════════════════════════════

class LoginScreen(BaseScreen):
    def _build(self):
        self._lbl(self, "🏦", size=40).pack(pady=(50, 0))
        self._lbl(self, "Мини-Банк", size=24, bold=True).pack()
        self._lbl(self, "Войдите в аккаунт",
                  color=Colors.TEXT2).pack(pady=(5, 30))

        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=40)

        self._lbl(form, "Телефон", size=11).pack(anchor="w")
        self.phone = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone.pack(fill="x", pady=(3, 12))

        self._lbl(form, "PIN-код", size=11).pack(anchor="w")
        self.pin = StyledEntry(form, placeholder="••••", show_char="•")
        self.pin.pack(fill="x", pady=(3, 20))

        StyledButton(form, text="Войти", command=self._login).pack(fill="x")

        bottom = tk.Frame(self, bg=Colors.BG)
        bottom.pack(pady=15)
        self._lbl(bottom, "Нет аккаунта?", color=Colors.TEXT2).pack(side="left")
        tk.Button(bottom, text="Регистрация", bg=Colors.BG, fg=Colors.ACCENT,
                  font=("Arial", 11, "underline"), relief="flat",
                  cursor="hand2", bd=0, activebackground=Colors.BG,
                  command=lambda: self.app.show("register")).pack(
            side="left", padx=5)

    def _login(self):
        ph = self.phone.val().replace(" ", "").replace("-", "")
        pin = self.pin.val()
        if not ph or not pin:
            messagebox.showerror("Ошибка", "Заполните поля!")
            return
        user = self.app.db.authenticate(ph, pin)
        if user:
            self.app.current_user = user
            self.app.show("dashboard")
        else:
            messagebox.showerror("Ошибка", "Неверный номер или PIN!")


# ══════════════════════════════
#  РЕГИСТРАЦИЯ
# ══════════════════════════════

class RegisterScreen(BaseScreen):
    def _build(self):
        self._lbl(self, "🏦", size=36).pack(pady=(30, 0))
        self._lbl(self, "Регистрация", size=20, bold=True).pack(pady=(5, 15))

        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=40)

        for lbl, ph, show in [
            ("Имя", "Ваше имя", None),
            ("Фамилия", "Фамилия", None),
            ("Телефон", "+992XXXXXXXXX", None),
            (f"PIN ({Config.PIN_LENGTH} цифры)", "••••", "•"),
        ]:
            self._lbl(form, lbl, size=11).pack(anchor="w")
            e = StyledEntry(form, placeholder=ph, show_char=show)
            e.pack(fill="x", pady=(3, 8))
            setattr(self, f"_{lbl[:3].lower()}", e)

        StyledButton(form, text="Зарегистрироваться",
                     command=self._register,
                     color=Colors.BTN_GREEN,
                     hover=Colors.BTN_GREEN_H).pack(fill="x", pady=(10, 0))

        bottom = tk.Frame(self, bg=Colors.BG)
        bottom.pack(pady=12)
        self._lbl(bottom, "Есть аккаунт?", color=Colors.TEXT2).pack(side="left")
        tk.Button(bottom, text="Войти", bg=Colors.BG, fg=Colors.ACCENT,
                  font=("Arial", 11, "underline"), relief="flat",
                  cursor="hand2", bd=0, activebackground=Colors.BG,
                  command=lambda: self.app.show("login")).pack(
            side="left", padx=5)

    def _register(self):
        f = self._имя.val()
        l = self._фам.val()
        ph = self._тел.val().replace(" ", "").replace("-", "")
        pin = self._pin.val()

        if not all([f, l, ph, pin]):
            messagebox.showerror("Ошибка", "Заполните все поля!")
            return
        if len(f) < 2 or len(l) < 2:
            messagebox.showerror("Ошибка", "Имя/фамилия: мин. 2 символа!")
            return
        if not (ph.startswith("+") and len(ph) >= 10 and ph[1:].isdigit()):
            messagebox.showerror("Ошибка", "Формат: +992XXXXXXXXX")
            return
        if not (pin.isdigit() and len(pin) == Config.PIN_LENGTH):
            messagebox.showerror("Ошибка",
                                 f"PIN = {Config.PIN_LENGTH} цифры!")
            return
        if self.app.db.phone_exists(ph):
            messagebox.showerror("Ошибка", "Номер уже занят!")
            return

        uid = self.app.db.gen_id()
        # GUI-регистрация: telegram_chat_id = None
        # Можно привязать позже через /start в боте
        user = User(uid, ph, f, l, pin, Config.INITIAL_BALANCE,
                    telegram_chat_id=None)
        self.app.db.save(user)
        self.app.log(f"🆕 Регистрация (GUI): {user.full_name()}")

        messagebox.showinfo("Успех",
            f"✅ Регистрация завершена!\n\n"
            f"{user.full_name()}\n{ph}\n"
            f"Баланс: {user.balance:,.2f} {Config.CURRENCY}\n\n"
            f"💡 Чтобы получать уведомления в Telegram,\n"
            f"напишите /start боту и привяжите аккаунт.")

        self.app.current_user = user
        self.app.show("dashboard")


# ══════════════════════════════
#  КОШЕЛЁК
# ══════════════════════════════

class WalletContent(BaseScreen):
    def _build(self):
        u = self.app.current_user
        self._lbl(self, "💰 Кошелёк", size=18, bold=True).pack(pady=(25, 15))

        card = tk.Frame(self, bg=Colors.CARD, padx=25, pady=20)
        card.pack(fill="x", padx=25, pady=10)

        self._lbl(card, "Ваш баланс", size=12,
                  color=Colors.TEXT2, bg=Colors.CARD).pack(anchor="w")
        self._lbl(card, f"{u.balance:,.2f}", size=36,
                  bold=True, color=Colors.ACCENT, bg=Colors.CARD).pack(anchor="w")
        self._lbl(card, Config.CURRENCY, size=14,
                  color=Colors.TEXT2, bg=Colors.CARD).pack(anchor="w")

        tk.Frame(self, bg=Colors.BORDER, height=1).pack(
            fill="x", padx=25, pady=20)

        StyledButton(self, text="💸  Перевести деньги",
                     command=lambda: self.app.dashboard.show_tab("transfer"),
                     color=Colors.BTN_GREEN,
                     hover=Colors.BTN_GREEN_H).pack(fill="x", padx=25)


# ══════════════════════════════
#  ПЕРЕВОД + УВЕДОМЛЕНИЕ
# ══════════════════════════════

class TransferContent(BaseScreen):
    def _build(self):
        u = self.app.current_user
        self._lbl(self, "💸 Перевод", size=18, bold=True).pack(pady=(20, 10))
        self._lbl(self, f"Доступно: {u.balance:,.2f} {Config.CURRENCY}",
                  color=Colors.TEXT2).pack(pady=(0, 15))

        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=30)

        self._lbl(form, "Номер получателя", size=11).pack(anchor="w")
        self.phone = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone.pack(fill="x", pady=(3, 10))

        self._lbl(form, "Сумма", size=11).pack(anchor="w")
        self.amount = StyledEntry(form, placeholder="0.00")
        self.amount.pack(fill="x", pady=(3, 20))

        StyledButton(form, text="💸 Отправить",
                     command=self._send,
                     color=Colors.BTN_GREEN,
                     hover=Colors.BTN_GREEN_H).pack(fill="x", pady=(0, 8))

        StyledButton(form, text="← Назад",
                     command=lambda: self.app.dashboard.show_tab("wallet"),
                     color=Colors.BTN_GRAY,
                     hover="#37474f").pack(fill="x")

    def _send(self):
        ph = self.phone.val().replace(" ", "").replace("-", "")
        amt_t = self.amount.val().replace(",", ".")

        if not ph or not amt_t:
            messagebox.showerror("Ошибка", "Заполните все поля!")
            return

        try:
            amt = round(float(amt_t), 2)
            assert amt > 0
        except:
            messagebox.showerror("Ошибка", "Некорректная сумма!")
            return

        sender = self.app.current_user

        if sender.phone == ph:
            messagebox.showerror("Ошибка", "Нельзя себе!")
            return

        rcv = self.app.db.get_by_phone(ph)
        if not rcv:
            messagebox.showerror("Ошибка",
                "Нет пользователя с таким номером!")
            return

        if not sender.has_funds(amt):
            messagebox.showerror("Ошибка",
                f"Недостаточно средств!\n"
                f"Баланс: {sender.balance:,.2f}")
            return

        ok = messagebox.askyesno("Подтверждение",
            f"Перевести {amt:,.2f} {Config.CURRENCY}\n"
            f"→ {rcv.full_name()} ({rcv.phone})?")
        if not ok:
            return

        # ── Выполняем перевод ──
        sender.debit(amt)
        rcv.credit(amt)
        self.app.db.save(sender)
        self.app.db.save(rcv)

        txn = Transaction(sender.phone, sender.full_name(),
                          rcv.phone, rcv.full_name(), amt)
        self.app.history.add(sender.user_id, txn.fmt_sender())
        self.app.history.add(rcv.user_id, txn.fmt_receiver())

        self.app.current_user = sender

        # ═══════════════════════════════════════════
        #  ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ ПОЛУЧАТЕЛЮ В TELEGRAM!
        # ═══════════════════════════════════════════

        notified = False
        if self.app.tg_bot:
            notified = self.app.tg_bot.notify_user(
                rcv, sender.full_name(), amt
            )

        # Сообщение отправителю
        if notified:
            notify_text = "📨 Получатель уведомлён в Telegram!"
        else:
            notify_text = "⚠️ У получателя нет привязки к Telegram."

        self.app.log(
            f"💸 {sender.full_name()} → {rcv.full_name()}: "
            f"{amt} {Config.CURRENCY}"
        )

        messagebox.showinfo("Успех",
            f"✅ Переведено!\n\n"
            f"👤 {rcv.full_name()}\n"
            f"💰 {amt:,.2f} {Config.CURRENCY}\n"
            f"💵 Остаток: {sender.balance:,.2f} {Config.CURRENCY}\n\n"
            f"{notify_text}")

        self.app.dashboard.show_tab("wallet")


# ══════════════════════════════
#  ИСТОРИЯ
# ══════════════════════════════

class HistoryContent(BaseScreen):
    def _build(self):
        u = self.app.current_user
        self._lbl(self, "📋 История", size=18, bold=True).pack(pady=(20, 10))

        container = tk.Frame(self, bg=Colors.BG)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        scroll = tk.Scrollbar(container)
        scroll.pack(side="right", fill="y")

        self.text = tk.Text(container, bg=Colors.CARD, fg=Colors.TEXT,
                            font=("Consolas", 11), relief="flat",
                            wrap="word", bd=10, state="disabled",
                            yscrollcommand=scroll.set)
        self.text.pack(fill="both", expand=True)
        scroll.config(command=self.text.yview)

        txt = self.app.history.get_all(u.user_id)
        self.text.configure(state="normal")
        self.text.insert("1.0", txt)
        self.text.configure(state="disabled")


# ══════════════════════════════
#  ПРОФИЛЬ
# ══════════════════════════════

class ProfileContent(BaseScreen):
    def _build(self):
        u = self.app.current_user
        self._lbl(self, "👤 Профиль", size=18, bold=True).pack(pady=(20, 15))

        initials = f"{u.first_name[0]}{u.last_name[0]}".upper()
        av = tk.Frame(self, bg=Colors.ACCENT, width=80, height=80)
        av.pack(pady=(5, 5))
        av.pack_propagate(False)
        self._lbl(av, initials, size=28, bold=True,
                  color="#1a237e", bg=Colors.ACCENT).place(
            relx=0.5, rely=0.5, anchor="center")

        self._lbl(self, u.full_name(), size=18, bold=True).pack(pady=(10, 3))
        self._lbl(self, u.phone, color=Colors.TEXT2).pack()

        # Статус Telegram
        tg_status = ("✅ Telegram привязан"
                     if u.telegram_chat_id
                     else "❌ Telegram не привязан\n"
                          "(напишите /start боту)")
        self._lbl(self, tg_status, size=10,
                  color=Colors.ACCENT if u.telegram_chat_id
                  else Colors.TEXT2).pack(pady=(5, 15))

        tk.Frame(self, bg=Colors.BORDER, height=1).pack(
            fill="x", padx=30, pady=5)

        info = tk.Frame(self, bg=Colors.BG)
        info.pack(fill="x", padx=35, pady=10)

        fields = [
            ("🆔  ID", str(u.user_id)),
            ("👤  Имя", u.first_name),
            ("👤  Фамилия", u.last_name),
            ("📱  Телефон", u.phone),
            ("💰  Баланс", f"{u.balance:,.2f} {Config.CURRENCY}"),
            ("📅  Дата", u.created_at),
        ]
        for lbl, val in fields:
            row = tk.Frame(info, bg=Colors.BG)
            row.pack(fill="x", pady=4)
            self._lbl(row, lbl, size=11, color=Colors.TEXT2).pack(side="left")
            self._lbl(row, val, size=12).pack(side="right")

        tk.Frame(self, bg=Colors.BORDER, height=1).pack(
            fill="x", padx=30, pady=15)

        StyledButton(self, text="🚪 Выйти",
                     command=self._logout,
                     color=Colors.BTN_RED,
                     hover=Colors.BTN_RED_H).pack(padx=60, fill="x")

    def _logout(self):
        self.app.current_user = None
        self.app.show("login")


# ══════════════════════════════
#  DASHBOARD — 3 ВКЛАДКИ ВНИЗУ
# ══════════════════════════════

class DashboardScreen(BaseScreen):
    def __init__(self, parent, app):
        self._nav = {}
        self._cur = "wallet"
        super().__init__(parent, app)

    def _build(self):
        self._content = tk.Frame(self, bg=Colors.BG)
        self._content.pack(fill="both", expand=True)

        # ═══ 3 КНОПКИ ВНИЗУ ═══
        nav = tk.Frame(self, bg=Colors.NAV_BG, height=55)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)

        for key, text in [("wallet", "💰 Кошелёк"),
                          ("history", "📋 История"),
                          ("profile", "👤 Профиль")]:
            btn = NavButton(nav, text=text,
                            command=lambda k=key: self.show_tab(k),
                            active=(key == "wallet"))
            btn.pack(side="left", fill="both", expand=True)
            self._nav[key] = btn

        self.show_tab("wallet")

    def show_tab(self, name):
        if self.app.current_user:
            fresh = self.app.db.get(self.app.current_user.user_id)
            if fresh:
                self.app.current_user = fresh

        self._cur = name
        for k, b in self._nav.items():
            b.set_active(k == name)

        for w in self._content.winfo_children():
            w.destroy()

        tabs = {
            "wallet": WalletContent,
            "transfer": TransferContent,
            "history": HistoryContent,
            "profile": ProfileContent,
        }
        cls = tabs.get(name, WalletContent)
        cls(self._content, self.app).pack(fill="both", expand=True)


# ══════════════════════════════════════════
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════

class BankApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🏦 Мини-Банк")
        self.geometry("420x700")
        self.resizable(False, False)
        self.configure(bg=Colors.BG)
        self._center()

        self.db = UserDatabase()
        self.history = HistoryManager()
        self.current_user = None
        self.dashboard = None
        self.tg_bot = None

        self._container = tk.Frame(self, bg=Colors.BG)
        self._container.pack(fill="both", expand=True)

        self._status = tk.Label(
            self, text="🤖 Telegram: запуск...",
            bg="#070b1e", fg=Colors.TEXT2,
            font=("Arial", 9), anchor="w", padx=10)
        self._status.pack(fill="x", side="bottom")

        self.show("login")
        self._start_telegram()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 420) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"+{x}+{y}")

    def show(self, name):
        for w in self._container.winfo_children():
            w.destroy()

        screens = {
            "login": LoginScreen,
            "register": RegisterScreen,
            "dashboard": DashboardScreen,
        }
        cls = screens.get(name)
        if cls:
            scr = cls(self._container, self)
            scr.pack(fill="both", expand=True)
            if name == "dashboard":
                self.dashboard = scr

    def log(self, msg):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")
        try:
            self._status.configure(text=f"🤖 {msg}")
        except:
            pass

    def _start_telegram(self):
        try:
            self.tg_bot = TelegramBot(
                self.db, self.history,
                log_cb=lambda m: self.after(0, lambda: self.log(m))
            )
            t = threading.Thread(target=self.tg_bot.run, daemon=True)
            t.start()
            self.log("Telegram-бот подключён ✅")
        except Exception as e:
            self.log(f"Ошибка Telegram: {e}")