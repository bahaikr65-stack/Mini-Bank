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
    """Поле ввода с подсказкой (placeholder)."""

    def __init__(self, parent, placeholder="", show_char=None, **kwargs):
        self.placeholder = placeholder
        self.show_char = show_char
        self.is_placeholder = False

        # Настройки внешнего вида
        style = {
            "bg": Colors.INPUT_BG,
            "fg": Colors.TEXT,
            "insertbackground": Colors.TEXT,
            "font": ("Arial", 13),
            "relief": "flat",
            "bd": 10,
            "highlightthickness": 2,
            "highlightcolor": Colors.ACCENT,
            "highlightbackground": Colors.BORDER
        }
        style.update(kwargs)
        super().__init__(parent, **style)

        # Если есть подсказка — показываем её
        if placeholder:
            self.show_placeholder()
            self.bind("<FocusIn>", self.on_focus_in)
            self.bind("<FocusOut>", self.on_focus_out)

    def show_placeholder(self):
        """Показывает текст-подсказку серым цветом."""
        self.is_placeholder = True
        self.configure(show="", fg=Colors.TEXT2)
        self.insert(0, self.placeholder)

    def on_focus_in(self, event=None):
        """Когда пользователь кликнул на поле — убираем подсказку."""
        if self.is_placeholder:
            self.delete(0, tk.END)
            self.configure(fg=Colors.TEXT)
            if self.show_char:
                self.configure(show=self.show_char)
            self.is_placeholder = False

    def on_focus_out(self, event=None):
        """Когда пользователь ушёл из поля — возвращаем подсказку если пусто."""
        if not self.get():
            self.show_placeholder()

    def get_value(self):
        """Возвращает текст из поля (пустую строку если там подсказка)."""
        if self.is_placeholder:
            return ""
        return self.get().strip()


class StyledButton(tk.Button):
    """Красивая кнопка с эффектом наведения."""

    def __init__(self, parent, text="", command=None,
                 color=None, hover=None, **kwargs):
        self.normal_color = color or Colors.BTN
        self.hover_color = hover or Colors.BTN_HOVER

        style = {
            "bg": self.normal_color,
            "fg": "white",
            "font": ("Arial", 13, "bold"),
            "relief": "flat",
            "cursor": "hand2",
            "bd": 0,
            "activebackground": self.hover_color,
            "activeforeground": "white",
            "pady": 12
        }
        style.update(kwargs)
        super().__init__(parent, text=text, command=command, **style)

        # Эффект наведения мышки
        self.bind("<Enter>", lambda event: self.configure(bg=self.hover_color))
        self.bind("<Leave>", lambda event: self.configure(bg=self.normal_color))


class NavButton(tk.Button):
    """Кнопка навигации внизу экрана."""

    def __init__(self, parent, text="", command=None, active=False, **kwargs):
        if active:
            bg_color = Colors.NAV_ACTIVE
            text_color = Colors.TEXT
        else:
            bg_color = Colors.NAV_BG
            text_color = Colors.NAV_INACTIVE

        super().__init__(
            parent, text=text, command=command,
            bg=bg_color, fg=text_color,
            font=("Arial", 11, "bold"),
            relief="flat", cursor="hand2", bd=0, pady=14,
            activebackground=Colors.NAV_ACTIVE,
            activeforeground=Colors.TEXT, **kwargs
        )

    def set_active(self, is_active):
        """Переключает вид кнопки: активная или нет."""
        if is_active:
            self.configure(bg=Colors.NAV_ACTIVE, fg=Colors.TEXT)
        else:
            self.configure(bg=Colors.NAV_BG, fg=Colors.NAV_INACTIVE)


# ══════════════════════════════
#  БАЗОВЫЙ ЭКРАН
# ══════════════════════════════

class BaseScreen(tk.Frame):
    """Базовый класс для всех экранов приложения."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=Colors.BG)
        self.app = app
        self.build()

    def build(self):
        """Переопределяется в дочерних классах."""
        pass

    def make_label(self, parent, text, size=12, bold=False,
                   color=Colors.TEXT, bg=Colors.BG):
        """Создаёт текстовую метку."""
        if bold:
            weight = "bold"
        else:
            weight = "normal"
        return tk.Label(parent, text=text, bg=bg, fg=color,
                        font=("Arial", size, weight))


# ══════════════════════════════
#  ЭКРАН ВХОДА
# ══════════════════════════════

class LoginScreen(BaseScreen):

    def build(self):
        # Заголовок
        self.make_label(self, "🏦", size=40).pack(pady=(50, 0))
        self.make_label(self, "Мини-Банк", size=24, bold=True).pack()
        self.make_label(self, "Войдите в аккаунт",
                        color=Colors.TEXT2).pack(pady=(5, 30))

        # Форма входа
        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=40)

        # Поле телефона
        self.make_label(form, "Телефон", size=11).pack(anchor="w")
        self.phone_entry = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone_entry.pack(fill="x", pady=(3, 12))

        # Поле PIN-кода
        self.make_label(form, "PIN-код", size=11).pack(anchor="w")
        self.pin_entry = StyledEntry(form, placeholder="••••", show_char="•")
        self.pin_entry.pack(fill="x", pady=(3, 20))

        # Кнопка входа
        StyledButton(form, text="Войти", command=self.on_login).pack(fill="x")

        # Ссылка на регистрацию
        bottom = tk.Frame(self, bg=Colors.BG)
        bottom.pack(pady=15)
        self.make_label(bottom, "Нет аккаунта?", color=Colors.TEXT2).pack(side="left")
        tk.Button(
            bottom, text="Регистрация", bg=Colors.BG, fg=Colors.ACCENT,
            font=("Arial", 11, "underline"), relief="flat",
            cursor="hand2", bd=0, activebackground=Colors.BG,
            command=lambda: self.app.show("register")
        ).pack(side="left", padx=5)

    def on_login(self):
        """Обработка нажатия кнопки Войти."""
        phone = self.phone_entry.get_value().replace(" ", "").replace("-", "")
        pin = self.pin_entry.get_value()

        # Проверяем что поля заполнены
        if not phone or not pin:
            messagebox.showerror("Ошибка", "Заполните поля!")
            return

        # Пробуем войти
        user = self.app.db.authenticate(phone, pin)
        if user:
            self.app.current_user = user
            self.app.show("dashboard")
        else:
            messagebox.showerror("Ошибка", "Неверный номер или PIN!")


# ══════════════════════════════
#  ЭКРАН РЕГИСТРАЦИИ
# ══════════════════════════════

class RegisterScreen(BaseScreen):

    def build(self):
        # Заголовок
        self.make_label(self, "🏦", size=36).pack(pady=(30, 0))
        self.make_label(self, "Регистрация", size=20, bold=True).pack(pady=(5, 15))

        # Форма регистрации
        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=40)

        # Поле имени
        self.make_label(form, "Имя", size=11).pack(anchor="w")
        self.name_entry = StyledEntry(form, placeholder="Ваше имя")
        self.name_entry.pack(fill="x", pady=(3, 8))

        # Поле фамилии
        self.make_label(form, "Фамилия", size=11).pack(anchor="w")
        self.surname_entry = StyledEntry(form, placeholder="Фамилия")
        self.surname_entry.pack(fill="x", pady=(3, 8))

        # Поле телефона
        self.make_label(form, "Телефон", size=11).pack(anchor="w")
        self.phone_entry = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone_entry.pack(fill="x", pady=(3, 8))

        # Поле PIN-кода
        self.make_label(form, f"PIN ({Config.PIN_LENGTH} цифры)", size=11).pack(anchor="w")
        self.pin_entry = StyledEntry(form, placeholder="••••", show_char="•")
        self.pin_entry.pack(fill="x", pady=(3, 8))

        # Кнопка регистрации
        StyledButton(
            form, text="Зарегистрироваться",
            command=self.on_register,
            color=Colors.BTN_GREEN,
            hover=Colors.BTN_GREEN_H
        ).pack(fill="x", pady=(10, 0))

        # Ссылка на вход
        bottom = tk.Frame(self, bg=Colors.BG)
        bottom.pack(pady=12)
        self.make_label(bottom, "Есть аккаунт?", color=Colors.TEXT2).pack(side="left")
        tk.Button(
            bottom, text="Войти", bg=Colors.BG, fg=Colors.ACCENT,
            font=("Arial", 11, "underline"), relief="flat",
            cursor="hand2", bd=0, activebackground=Colors.BG,
            command=lambda: self.app.show("login")
        ).pack(side="left", padx=5)

    def on_register(self):
        """Обработка нажатия кнопки Зарегистрироваться."""
        first_name = self.name_entry.get_value()
        last_name = self.surname_entry.get_value()
        phone = self.phone_entry.get_value().replace(" ", "").replace("-", "")
        pin = self.pin_entry.get_value()

        # Проверки
        if not first_name or not last_name or not phone or not pin:
            messagebox.showerror("Ошибка", "Заполните все поля!")
            return

        if len(first_name) < 2 or len(last_name) < 2:
            messagebox.showerror("Ошибка", "Имя/фамилия: мин. 2 символа!")
            return

        if not (phone.startswith("+") and len(phone) >= 10 and phone[1:].isdigit()):
            messagebox.showerror("Ошибка", "Формат: +992XXXXXXXXX")
            return

        if not (pin.isdigit() and len(pin) == Config.PIN_LENGTH):
            messagebox.showerror("Ошибка", f"PIN = {Config.PIN_LENGTH} цифры!")
            return

        if self.app.db.phone_exists(phone):
            messagebox.showerror("Ошибка", "Номер уже занят!")
            return

        # Создаём пользователя
        user_id = self.app.db.gen_id()
        user = User(user_id, phone, first_name, last_name, pin,
                    Config.INITIAL_BALANCE, telegram_chat_id=None)
        self.app.db.save(user)
        self.app.log(f"🆕 Регистрация (GUI): {user.full_name()}")

        # Показываем сообщение об успехе
        messagebox.showinfo("Успех",
            f"✅ Регистрация завершена!\n\n"
            f"{user.full_name()}\n{phone}\n"
            f"Баланс: {user.balance:,.2f} {Config.CURRENCY}\n\n"
            f"💡 Чтобы получать уведомления в Telegram,\n"
            f"напишите /start боту и привяжите аккаунт.")

        # Переходим на главный экран
        self.app.current_user = user
        self.app.show("dashboard")


# ══════════════════════════════
#  КОШЕЛЁК
# ══════════════════════════════

class WalletContent(BaseScreen):

    def build(self):
        user = self.app.current_user

        self.make_label(self, "💰 Кошелёк", size=18, bold=True).pack(pady=(25, 15))

        # Карточка с балансом
        card = tk.Frame(self, bg=Colors.CARD, padx=25, pady=20)
        card.pack(fill="x", padx=25, pady=10)

        self.make_label(card, "Ваш баланс", size=12,
                        color=Colors.TEXT2, bg=Colors.CARD).pack(anchor="w")
        self.make_label(card, f"{user.balance:,.2f}", size=36,
                        bold=True, color=Colors.ACCENT, bg=Colors.CARD).pack(anchor="w")
        self.make_label(card, Config.CURRENCY, size=14,
                        color=Colors.TEXT2, bg=Colors.CARD).pack(anchor="w")

        # Разделитель
        tk.Frame(self, bg=Colors.BORDER, height=1).pack(
            fill="x", padx=25, pady=20)

        # Кнопка перевода
        StyledButton(
            self, text="💸  Перевести деньги",
            command=lambda: self.app.dashboard.show_tab("transfer"),
            color=Colors.BTN_GREEN,
            hover=Colors.BTN_GREEN_H
        ).pack(fill="x", padx=25)


# ══════════════════════════════
#  ПЕРЕВОД
# ══════════════════════════════

class TransferContent(BaseScreen):

    def build(self):
        user = self.app.current_user

        self.make_label(self, "💸 Перевод", size=18, bold=True).pack(pady=(20, 10))
        self.make_label(self, f"Доступно: {user.balance:,.2f} {Config.CURRENCY}",
                        color=Colors.TEXT2).pack(pady=(0, 15))

        # Форма перевода
        form = tk.Frame(self, bg=Colors.BG)
        form.pack(fill="x", padx=30)

        # Номер получателя
        self.make_label(form, "Номер получателя", size=11).pack(anchor="w")
        self.phone_entry = StyledEntry(form, placeholder="+992XXXXXXXXX")
        self.phone_entry.pack(fill="x", pady=(3, 10))

        # Сумма перевода
        self.make_label(form, "Сумма", size=11).pack(anchor="w")
        self.amount_entry = StyledEntry(form, placeholder="0.00")
        self.amount_entry.pack(fill="x", pady=(3, 20))

        # Кнопка отправки
        StyledButton(
            form, text="💸 Отправить",
            command=self.on_send,
            color=Colors.BTN_GREEN,
            hover=Colors.BTN_GREEN_H
        ).pack(fill="x", pady=(0, 8))

        # Кнопка назад
        StyledButton(
            form, text="← Назад",
            command=lambda: self.app.dashboard.show_tab("wallet"),
            color=Colors.BTN_GRAY,
            hover="#37474f"
        ).pack(fill="x")

    def on_send(self):
        """Обработка нажатия кнопки Отправить."""
        phone = self.phone_entry.get_value().replace(" ", "").replace("-", "")
        amount_text = self.amount_entry.get_value().replace(",", ".")

        # Проверяем что поля заполнены
        if not phone or not amount_text:
            messagebox.showerror("Ошибка", "Заполните все поля!")
            return

        # Проверяем что сумма корректная
        try:
            amount = round(float(amount_text), 2)
            assert amount > 0
        except:
            messagebox.showerror("Ошибка", "Некорректная сумма!")
            return

        sender = self.app.current_user

        # Нельзя переводить самому себе
        if sender.phone == phone:
            messagebox.showerror("Ошибка", "Нельзя себе!")
            return

        # Ищем получателя в базе
        receiver = self.app.db.get_by_phone(phone)
        if not receiver:
            messagebox.showerror("Ошибка", "Нет пользователя с таким номером!")
            return

        # Проверяем достаточно ли денег
        if not sender.has_funds(amount):
            messagebox.showerror("Ошибка",
                f"Недостаточно средств!\n"
                f"Баланс: {sender.balance:,.2f}")
            return

        # Спрашиваем подтверждение
        confirm = messagebox.askyesno("Подтверждение",
            f"Перевести {amount:,.2f} {Config.CURRENCY}\n"
            f"→ {receiver.full_name()} ({receiver.phone})?")
        if not confirm:
            return

        # ── Выполняем перевод ──
        sender.debit(amount)
        receiver.credit(amount)
        self.app.db.save(sender)
        self.app.db.save(receiver)

        # Записываем в историю
        transaction = Transaction(sender.phone, sender.full_name(),
                                  receiver.phone, receiver.full_name(), amount)
        self.app.history.add(sender.user_id, transaction.fmt_sender())
        self.app.history.add(receiver.user_id, transaction.fmt_receiver())

        self.app.current_user = sender

        # ── Отправляем уведомление в Telegram ──
        notified = False
        if self.app.tg_bot:
            notified = self.app.tg_bot.notify_user(
                receiver, sender.full_name(), amount
            )

        if notified:
            notify_text = "📨 Получатель уведомлён в Telegram!"
        else:
            notify_text = "⚠️ У получателя нет привязки к Telegram."

        self.app.log(
            f"💸 {sender.full_name()} → {receiver.full_name()}: "
            f"{amount} {Config.CURRENCY}"
        )

        # Показываем результат
        messagebox.showinfo("Успех",
            f"✅ Переведено!\n\n"
            f"👤 {receiver.full_name()}\n"
            f"💰 {amount:,.2f} {Config.CURRENCY}\n"
            f"💵 Остаток: {sender.balance:,.2f} {Config.CURRENCY}\n\n"
            f"{notify_text}")

        self.app.dashboard.show_tab("wallet")


# ══════════════════════════════
#  ИСТОРИЯ
# ══════════════════════════════

class HistoryContent(BaseScreen):

    def build(self):
        user = self.app.current_user

        self.make_label(self, "📋 История", size=18, bold=True).pack(pady=(20, 10))

        # Контейнер для текста с прокруткой
        container = tk.Frame(self, bg=Colors.BG)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        scrollbar = tk.Scrollbar(container)
        scrollbar.pack(side="right", fill="y")

        text_widget = tk.Text(
            container, bg=Colors.CARD, fg=Colors.TEXT,
            font=("Consolas", 11), relief="flat",
            wrap="word", bd=10, state="disabled",
            yscrollcommand=scrollbar.set
        )
        text_widget.pack(fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)

        # Загружаем историю из базы
        history_text = self.app.history.get_all(user.user_id)
        text_widget.configure(state="normal")
        text_widget.insert("1.0", history_text)
        text_widget.configure(state="disabled")


# ══════════════════════════════
#  ПРОФИЛЬ
# ══════════════════════════════

class ProfileContent(BaseScreen):

    def build(self):
        user = self.app.current_user

        self.make_label(self, "👤 Профиль", size=18, bold=True).pack(pady=(20, 15))

        # Аватар с инициалами
        initials = (user.first_name[0] + user.last_name[0]).upper()
        avatar_frame = tk.Frame(self, bg=Colors.ACCENT, width=80, height=80)
        avatar_frame.pack(pady=(5, 5))
        avatar_frame.pack_propagate(False)
        self.make_label(avatar_frame, initials, size=28, bold=True,
                        color="#1a237e", bg=Colors.ACCENT).place(
            relx=0.5, rely=0.5, anchor="center")

        # Имя и телефон
        self.make_label(self, user.full_name(), size=18, bold=True).pack(pady=(10, 3))
        self.make_label(self, user.phone, color=Colors.TEXT2).pack()

        # Статус привязки Telegram
        if user.telegram_chat_id:
            telegram_status = "✅ Telegram привязан"
            status_color = Colors.ACCENT
        else:
            telegram_status = "❌ Telegram не привязан\n(напишите /start боту)"
            status_color = Colors.TEXT2

        self.make_label(self, telegram_status, size=10,
                        color=status_color).pack(pady=(5, 15))

        # Разделитель
        tk.Frame(self, bg=Colors.BORDER, height=1).pack(
            fill="x", padx=30, pady=5)

        # Информация о пользователе
        info_frame = tk.Frame(self, bg=Colors.BG)
        info_frame.pack(fill="x", padx=35, pady=10)

        fields = [
            ("🆔  ID", str(user.user_id)),
            ("👤  Имя", user.first_name),
            ("👤  Фамилия", user.last_name),
            ("📱  Телефон", user.phone),
            ("💰  Баланс", f"{user.balance:,.2f} {Config.CURRENCY}"),
            ("📅  Дата", user.created_at),
        ]

        for label_text, value_text in fields:
            row = tk.Frame(info_frame, bg=Colors.BG)
            row.pack(fill="x", pady=4)
            self.make_label(row, label_text, size=11, color=Colors.TEXT2).pack(side="left")
            self.make_label(row, value_text, size=12).pack(side="right")

        # Разделитель
        tk.Frame(self, bg=Colors.BORDER, height=1).pack(
            fill="x", padx=30, pady=15)

        # Кнопка выхода
        StyledButton(
            self, text="🚪 Выйти",
            command=self.on_logout,
            color=Colors.BTN_RED,
            hover=Colors.BTN_RED_H
        ).pack(padx=60, fill="x")

    def on_logout(self):
        """Выход из аккаунта."""
        self.app.current_user = None
        self.app.show("login")


# ══════════════════════════════
#  DASHBOARD — 3 ВКЛАДКИ ВНИЗУ
# ══════════════════════════════

class DashboardScreen(BaseScreen):

    def __init__(self, parent, app):
        self.nav_buttons = {}
        self.current_tab = "wallet"
        super().__init__(parent, app)

    def build(self):
        # Область для содержимого вкладок
        self.content_frame = tk.Frame(self, bg=Colors.BG)
        self.content_frame.pack(fill="both", expand=True)

        # ═══ 3 КНОПКИ НАВИГАЦИИ ВНИЗУ ═══
        nav_bar = tk.Frame(self, bg=Colors.NAV_BG, height=55)
        nav_bar.pack(fill="x", side="bottom")
        nav_bar.pack_propagate(False)

        tabs = [
            ("wallet", "💰 Кошелёк"),
            ("history", "📋 История"),
            ("profile", "👤 Профиль"),
        ]

        for tab_key, tab_text in tabs:
            is_active = (tab_key == "wallet")
            button = NavButton(
                nav_bar, text=tab_text,
                command=lambda key=tab_key: self.show_tab(key),
                active=is_active
            )
            button.pack(side="left", fill="both", expand=True)
            self.nav_buttons[tab_key] = button

        # Показываем кошелёк по умолчанию
        self.show_tab("wallet")

    def show_tab(self, tab_name):
        """Переключает вкладку на dashboard."""

        # Обновляем данные пользователя из базы
        if self.app.current_user:
            fresh_user = self.app.db.get(self.app.current_user.user_id)
            if fresh_user:
                self.app.current_user = fresh_user

        self.current_tab = tab_name

        # Обновляем вид кнопок навигации
        for key, button in self.nav_buttons.items():
            button.set_active(key == tab_name)

        # Очищаем содержимое
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Выбираем какую вкладку показать
        if tab_name == "wallet":
            tab_class = WalletContent
        elif tab_name == "transfer":
            tab_class = TransferContent
        elif tab_name == "history":
            tab_class = HistoryContent
        elif tab_name == "profile":
            tab_class = ProfileContent
        else:
            tab_class = WalletContent

        # Создаём и показываем вкладку
        tab = tab_class(self.content_frame, self.app)
        tab.pack(fill="both", expand=True)


# ══════════════════════════════════════════
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════

class BankApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("🏦 Мини-Банк")
        self.geometry("420x600")
        self.resizable(False, False)
        self.configure(bg=Colors.BG)
        self.center_window()

        # Инициализация базы данных и переменных
        self.db = UserDatabase()
        self.history = HistoryManager()
        self.current_user = None
        self.dashboard = None
        self.tg_bot = None

        # Контейнер для экранов
        self.main_container = tk.Frame(self, bg=Colors.BG)
        self.main_container.pack(fill="both", expand=True)

        # Статус-бар внизу окна
        self.status_label = tk.Label(
            self, text="🤖 Telegram: запуск...",
            bg="#070b1e", fg=Colors.TEXT2,
            font=("Arial", 9), anchor="w", padx=10
        )
        self.status_label.pack(fill="x", side="bottom")

        # Показываем экран входа
        self.show("login")

        # Запускаем Telegram-бота
        self.start_telegram_bot()

    def center_window(self):
        """Центрирует окно на экране."""
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 420) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"+{x}+{y}")

    def show(self, screen_name):
        """Переключает экран приложения."""
        # Удаляем всё из контейнера
        for widget in self.main_container.winfo_children():
            widget.destroy()

        # Выбираем нужный экран
        if screen_name == "login":
            screen_class = LoginScreen
        elif screen_name == "register":
            screen_class = RegisterScreen
        elif screen_name == "dashboard":
            screen_class = DashboardScreen
        else:
            return

        # Создаём и показываем экран
        screen = screen_class(self.main_container, self)
        screen.pack(fill="both", expand=True)

        # Сохраняем ссылку на dashboard
        if screen_name == "dashboard":
            self.dashboard = screen

    def log(self, message):
        """Выводит сообщение в консоль и статус-бар."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        try:
            self.status_label.configure(text=f"🤖 {message}")
        except:
            pass

    def start_telegram_bot(self):
        """Запускает Telegram-бота в отдельном потоке."""
        try:
            self.tg_bot = TelegramBot(
                self.db, self.history,
                log_cb=lambda message: self.after(0, lambda: self.log(message))
            )
            bot_thread = threading.Thread(target=self.tg_bot.run, daemon=True)
            bot_thread.start()
            self.log("Telegram-бот подключён ✅")
        except Exception as error:
            self.log(f"Ошибка Telegram: {error}")