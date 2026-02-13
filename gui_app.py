import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
from config import Config, Colors
from models import User, Transaction
from database import UserDatabase, HistoryManager
from telegram_bot import TelegramBot


# ══════════════════════════════════════════
#  БАЗОВЫЕ ВИДЖЕТЫ
# ══════════════════════════════════════════

class StyledEntry(tk.Entry):
    """Поле ввода с placeholder"""

    def __init__(self, parent, placeholder="", show_char=None, **kw):
        self._ph = placeholder
        self._show = show_char
        self._is_ph = False
        defaults = dict(bg=Colors.INPUT_BG, fg=Colors.TEXT,
                        insertbackground=Colors.TEXT,
                        font=("Arial", 13), relief="flat", bd=10,
                        highlightthickness=2, highlightcolor=Colors.ACCENT,
                        highlightbackground=Colors.BORDER)
        defaults.update(kw)
        super().__init__(parent, **defaults)
        if placeholder:
            self._show_ph()
            self.bind("<FocusIn>", self._focus_in)
            self.bind("<FocusOut>", self._focus_out)

    def _show_ph(self):
        self._is_ph = True
        self.configure(show="", fg=Colors.TEXT2)
        self.insert(0, self._ph)

    def _focus_in(self, e=None):
        if self._is_ph:
            self.delete(0, tk.END)
            self.configure(fg=Colors.TEXT)
            if self._show:
                self.configure(show=self._show)
            self._is_ph = False

    def _focus_out(self, e=None):
        if not self.get():
            self._show_ph()

    def val(self):
        return "" if self._is_ph else self.get().strip()

    def clear(self):
        self.delete(0, tk.END)
        if self._ph:
            self._show_ph()


class StyledButton(tk.Button):
    """Кнопка с hover"""

    def __init__(self, parent, text="", command=None,
                 color=None, hover=None, **kw):
        c = color or Colors.BTN
        h = hover or Colors.BTN_HOVER
        defaults = dict(bg=c, fg="white", font=("Arial", 13, "bold"),
                        relief="flat", cursor="hand2", bd=0,
                        activebackground=h, activeforeground="white", pady=12)
        defaults.update(kw)
        super().__init__(parent, text=text, command=command, **defaults)
        self.bind("<Enter>", lambda e: self.configure(bg=h))
        self.bind("<Leave>", lambda e: self.configure(bg=c))


class NavButton(tk.Button):
    """Кнопка нижней навигации"""

    def __init__(self, parent, text="", command=None, active=False, **kw):
        self._active = active
        bg = Colors.NAV_ACTIVE if active else Colors.NAV_BG
        fg = Colors.TEXT if active else Colors.NAV_INACTIVE
        super().__init__(parent, text=text, command=command,
                         bg=bg, fg=fg, font=("Arial", 11, "bold"),
                         relief="flat", cursor="hand2", bd=0, pady=14,
                         activebackground=Colors.NAV_ACTIVE,
                         activeforeground=Colors.TEXT, **kw)

    def set_active(self, active):
        self._active = active
        self.configure(
            bg=Colors.NAV_ACTIVE if active else Colors.NAV_BG,
            fg=Colors.TEXT if active else Colors.NAV_INACTIVE)



#  БАЗОВЫЙ ЭКРАН


class BaseScreen(tk.Frame):
    """Абстрактный экран"""

    def __init__(self, parent, app):
        super().__init__(parent, bg=Colors.BG)
        self.app = app
        self._build()

    def _build(self):
        pass

    def _label(self, parent, text, size=12, bold=False,
               color=Colors.TEXT, bg=Colors.BG):
        w = "bold" if bold else "normal"
        return tk.Label(parent, text=text, bg=bg, fg=color,
                        font=("Arial", size, w))



#  ЭКРАН ВХОДА


class LoginScreen(BaseScreen):
    def _build(self):
        self._label(self, "🏦", size=40).pack(pady=(50, 0))
        self._label(self, "Baha Bank", size=24, bold=True).pack()
        self._label(self, "Войдите в аккаунт",
                    color=Colors.TEXT2).pack(pady=(5, 30))

        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=40)

        self._label(form, "Номер телефона", size=11).pack(anchor="w")
        self.phone = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone.pack(fill="x", pady=(3, 12))

        self._label(form, "PIN-код", size=11).pack(anchor="w")
        self.pin = StyledEntry(form, placeholder="••••", show_char="•")
        self.pin.pack(fill="x", pady=(3, 20))

        StyledButton(form, text="Войти", command=self._login).pack(fill="x")

        bottom = tk.Frame(self, bg=Colors.BG)
        bottom.pack(pady=15)
        self._label(bottom, "Нет аккаунта?", color=Colors.TEXT2).pack(side="left")
        tk.Button(bottom, text="Регистрация", bg=Colors.BG, fg=Colors.ACCENT,
                  font=("Arial", 11, "underline"), relief="flat", cursor="hand2",
                  bd=0, command=lambda: self.app.show("register"),
                  activebackground=Colors.BG).pack(side="left", padx=5)

    def _login(self):
        ph = self.phone.val().replace(" ", "").replace("-", "")
        pin = self.pin.val()
        if not ph or not pin:
            messagebox.showerror("Ошибка", "Заполните все поля!")
            return
        user = self.app.db.authenticate(ph, pin)
        if user:
            self.app.current_user = user
            self.app.show("dashboard")
        else:
            messagebox.showerror("Ошибка", "Неверный номер или PIN!")



#  ЭКРАН РЕГИСТРАЦИИ


class RegisterScreen(BaseScreen):
    def _build(self):
        self._label(self, "🏦", size=36).pack(pady=(30, 0))
        self._label(self, "Регистрация", size=20, bold=True).pack(pady=(5, 15))

        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=40)

        self._label(form, "Имя", size=11).pack(anchor="w")
        self.first = StyledEntry(form, placeholder="Ваше имя")
        self.first.pack(fill="x", pady=(3, 8))

        self._label(form, "Фамилия", size=11).pack(anchor="w")
        self.last = StyledEntry(form, placeholder="Фамилия")
        self.last.pack(fill="x", pady=(3, 8))

        self._label(form, "Телефон", size=11).pack(anchor="w")
        self.phone = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone.pack(fill="x", pady=(3, 8))

        self._label(form, f"PIN ({Config.PIN_LENGTH} цифры)", size=11).pack(anchor="w")
        self.pin = StyledEntry(form, placeholder="••••", show_char="•")
        self.pin.pack(fill="x", pady=(3, 18))

        StyledButton(form, text="Зарегистрироваться",
                     command=self._register,
                     color=Colors.BTN_GREEN,
                     hover=Colors.BTN_GREEN_H).pack(fill="x")

        bottom = tk.Frame(self, bg=Colors.BG)
        bottom.pack(pady=12)
        self._label(bottom, "Есть аккаунт?", color=Colors.TEXT2).pack(side="left")
        tk.Button(bottom, text="Войти", bg=Colors.BG, fg=Colors.ACCENT,
                  font=("Arial", 11, "underline"), relief="flat", cursor="hand2",
                  bd=0, command=lambda: self.app.show("login"),
                  activebackground=Colors.BG).pack(side="left", padx=5)

# В классе RegisterScreen, метод _register():

    def _register(self):
        f = self.first.val()
        l = self.last.val()
        ph = self.phone.val().replace(" ", "").replace("-", "")
        pin = self.pin.val()

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
            messagebox.showerror("Ошибка", f"PIN = {Config.PIN_LENGTH} цифры!")
            return
        if self.app.db.phone_exists(ph):
            messagebox.showerror("Ошибка", "Номер уже зарегистрирован!")
            return

        uid = self.app.db.gen_id()
        # ИСПРАВЛЕНО: для GUI пользователей telegram_id = None
        user = User(uid, ph, f, l, pin, Config.INITIAL_BALANCE, telegram_id=None)
        self.app.db.save(user)
        self.app.log(f"🆕 Регистрация (GUI): {user.full_name()}")

        messagebox.showinfo("Успех",
            f"Регистрация завершена!\n\n"
            f"{user.full_name()}\n{ph}\n"
            f"Баланс: {user.balance:,.2f} {Config.CURRENCY}")

        self.app.current_user = user
        self.app.show("dashboard")



#  КОНТЕНТ КОШЕЛЬКА

class WalletContent(BaseScreen):
    def _build(self):
        u = self.app.current_user

        self._label(self, "💰 Кошелёк", size=18, bold=True).pack(pady=(25, 15))

        card = tk.Frame(self, bg=Colors.CARD, padx=25, pady=20)
        card.pack(fill="x", padx=25, pady=10)

        self._label(card, "Ваш баланс", size=12,
                    color=Colors.TEXT2, bg=Colors.CARD).pack(anchor="w")
        self._label(card, f"{u.balance:,.2f}", size=36,
                    bold=True, color=Colors.ACCENT, bg=Colors.CARD).pack(anchor="w")
        self._label(card, Config.CURRENCY, size=14,
                    color=Colors.TEXT2, bg=Colors.CARD).pack(anchor="w")

        tk.Frame(self, bg=Colors.BORDER, height=1).pack(fill="x", padx=25, pady=20)

        StyledButton(self, text="💸  Перевести деньги",
                     command=self._transfer,
                     color=Colors.BTN_GREEN,
                     hover=Colors.BTN_GREEN_H).pack(fill="x", padx=25)

    def _transfer(self):
        self.app.dashboard.show_tab("transfer")


#  КОНТЕНТ ПЕРЕВОДА

class TransferContent(BaseScreen):
    def _build(self):
        u = self.app.current_user

        self._label(self, "💸 Перевод", size=18, bold=True).pack(pady=(20, 10))
        self._label(self, f"Доступно: {u.balance:,.2f} {Config.CURRENCY}",
                    color=Colors.TEXT2).pack(pady=(0, 15))

        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=30)

        self._label(form, "Номер получателя", size=11).pack(anchor="w")
        self.phone = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone.pack(fill="x", pady=(3, 10))

        self._label(form, "Сумма", size=11).pack(anchor="w")
        self.amount = StyledEntry(form, placeholder="0.00")
        self.amount.pack(fill="x", pady=(3, 20))

        StyledButton(form, text="Отправить", command=self._send,
                     color=Colors.BTN_GREEN,
                     hover=Colors.BTN_GREEN_H).pack(fill="x", pady=(0, 8))

        StyledButton(form, text="Назад", command=self._back,
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

        sender.debit(amt)
        rcv.credit(amt)
        self.app.db.save(sender)
        self.app.db.save(rcv)

        txn = Transaction(sender.phone, sender.full_name(),
                          rcv.phone, rcv.full_name(), amt)
        self.app.history.add(sender.user_id, txn.fmt_sender())
        self.app.history.add(rcv.user_id, txn.fmt_receiver())

        self.app.current_user = sender
        self.app.log(
            f"💸 {sender.full_name()} → {rcv.full_name()}: {amt}")

        # Уведомить получателя в Telegram
        if self.app.tg_bot:
            try:
                self.app.tg_bot.bot.send_message(rcv.user_id,
                    f"📥 *Входящий перевод!*\n\n"
                    f"👤 От: {sender.full_name()}\n"
                    f"💰 +{amt:,.2f} {Config.CURRENCY}\n"
                    f"💵 Баланс: *{rcv.balance:,.2f} {Config.CURRENCY}*",
                    parse_mode="Markdown")
            except:
                pass

        messagebox.showinfo("Успех",
            f"✅ Переведено!\n\n"
            f"{rcv.full_name()}: {amt:,.2f} {Config.CURRENCY}\n"
            f"Остаток: {sender.balance:,.2f} {Config.CURRENCY}")

        self.app.dashboard.show_tab("wallet")

    def _back(self):
        self.app.dashboard.show_tab("wallet")


# ══════════════════════════════════════════
#  КОНТЕНТ ИСТОРИИ
# ══════════════════════════════════════════

class HistoryContent(BaseScreen):
    def _build(self):
        u = self.app.current_user

        self._label(self, "📋 История операций",
                    size=18, bold=True).pack(pady=(20, 10))

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


# ══════════════════════════════════════════
#  КОНТЕНТ ПРОФИЛЯ
# ══════════════════════════════════════════

class ProfileContent(BaseScreen):
    def _build(self):
        u = self.app.current_user

        self._label(self, "👤 Профиль",
                    size=18, bold=True).pack(pady=(20, 15))

        # Аватар
        initials = f"{u.first_name[0]}{u.last_name[0]}".upper()
        av = tk.Frame(self, bg=Colors.ACCENT, width=80, height=80)
        av.pack(pady=(5, 5))
        av.pack_propagate(False)
        self._label(av, initials, size=28, bold=True,
                    color="#1a237e", bg=Colors.ACCENT).place(
            relx=0.5, rely=0.5, anchor="center")

        self._label(self, u.full_name(), size=18, bold=True).pack(pady=(10, 3))
        self._label(self, u.phone, color=Colors.TEXT2).pack(pady=(0, 15))

        tk.Frame(self, bg=Colors.BORDER, height=1).pack(fill="x", padx=30, pady=5)

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
            self._label(row, lbl, size=11, color=Colors.TEXT2).pack(side="left")
            self._label(row, val, size=12).pack(side="right")

        tk.Frame(self, bg=Colors.BORDER, height=1).pack(fill="x", padx=30, pady=15)

        StyledButton(self, text="🚪  Выйти", command=self._logout,
                     color=Colors.BTN_RED, hover=Colors.BTN_RED_H).pack(padx=60, fill="x")

    def _logout(self):
        self.app.current_user = None
        self.app.show("login")


# ══════════════════════════════════════════
#  DASHBOARD — 3 ВКЛАДКИ ВНИЗУ
# ══════════════════════════════════════════

class DashboardScreen(BaseScreen):
    """
    Главный экран после входа.
    Внизу ВСЕГДА 3 кнопки-вкладки:
      💰 Кошелёк  |  📋 История  |  👤 Профиль
    """

    def __init__(self, parent, app):
        self._nav_btns = {}
        self._current = "wallet"
        super().__init__(parent, app)

    def _build(self):
        # Область контента (верх)
        self._content = tk.Frame(self, bg=Colors.BG)
        self._content.pack(fill="both", expand=True)

        # ═══ 3 КНОПКИ ВНИЗУ ═══
        nav = tk.Frame(self, bg=Colors.NAV_BG, height=55)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)

        tabs = [
            ("wallet", "💰 Кошелёк"),
            ("history", "📋 История"),
            ("profile", "👤 Профиль"),
        ]

        for key, text in tabs:
            btn = NavButton(nav, text=text,
                            command=lambda k=key: self.show_tab(k),
                            active=(key == "wallet"))
            btn.pack(side="left", fill="both", expand=True)
            self._nav_btns[key] = btn

        self.show_tab("wallet")

    def show_tab(self, name):
        """Переключить вкладку"""

        # Обновить юзера из БД
        if self.app.current_user:
            fresh = self.app.db.get(self.app.current_user.user_id)
            if fresh:
                self.app.current_user = fresh

        self._current = name

        # Обновить подсветку кнопок
        for key, btn in self._nav_btns.items():
            btn.set_active(key == name)

        # Очистить контент
        for w in self._content.winfo_children():
            w.destroy()

        # Показать нужный контент
        screens = {
            "wallet": WalletContent,
            "transfer": TransferContent,
            "history": HistoryContent,
            "profile": ProfileContent,
        }

        cls = screens.get(name, WalletContent)
        scr = cls(self._content, self.app)
        scr.pack(fill="both", expand=True)


# ══════════════════════════════════════════
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════

class BankApp(tk.Tk):
    """
    Главное окно приложения.
    Наследует tk.Tk.
    Запускает Telegram-бота в фоновом потоке.
    Содержит Tkinter GUI с 3 вкладками внизу.
    """

    def __init__(self):
        super().__init__()

        self.title("🏦 Мини-Банк")
        self.geometry("420x700")
        self.resizable(False, False)
        self.configure(bg=Colors.BG)
        self._center()

        # Компоненты
        self.db = UserDatabase()
        self.history = HistoryManager()
        self.current_user = None
        self.dashboard = None
        self.tg_bot = None
        self._logs = []

        # Контейнер
        self._container = tk.Frame(self, bg=Colors.BG)
        self._container.pack(fill="both", expand=True)

        # Статус-бар с логами
        self._status = tk.Label(self, text="🤖 Telegram: запуск...",
                                bg="#070b1e", fg=Colors.TEXT2,
                                font=("Arial", 9), anchor="w", padx=10)
        self._status.pack(fill="x", side="bottom")

        # Стартовый экран
        self.show("login")

        # Запускаем Telegram-бот
        self._start_telegram()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 420) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"+{x}+{y}")

    def show(self, name):
        """Переключить экран"""
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
        """Логирование"""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._logs.append(line)
        print(line)
        try:
            self._status.configure(text=f"🤖 {msg}")
        except:
            pass

    def _start_telegram(self):
        """Запуск Telegram-бота в отдельном потоке"""
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