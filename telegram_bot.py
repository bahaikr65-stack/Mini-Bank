import telebot
from telebot import types
from enum import Enum, auto
from config import Config
from models import User, Transaction
from database import UserDatabase, HistoryManager


class St(Enum):
    """Состояния диалога с пользователем."""
    IDLE = auto()
    REG_FIRST = auto()
    REG_LAST = auto()
    REG_PHONE = auto()
    REG_PIN = auto()
    TR_PHONE = auto()
    TR_AMOUNT = auto()
    TR_CONFIRM = auto()


class States:
    """Хранилище состояний и временных данных пользователей."""

    def __init__(self):
        self.user_states = {}
        self.user_data = {}

    def set(self, user_id, state):
        """Установить состояние пользователя."""
        self.user_states[user_id] = state

    def get(self, user_id):
        """Получить текущее состояние пользователя."""
        return self.user_states.get(user_id, St.IDLE)

    def reset(self, user_id):
        """Сбросить состояние и данные пользователя."""
        self.user_states[user_id] = St.IDLE
        self.user_data.pop(user_id, None)

    def save_data(self, user_id, key, value):
        """Сохранить временные данные пользователя."""
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id][key] = value

    def get_data(self, user_id, key=None):
        """Получить временные данные пользователя."""
        if key:
            return self.user_data.get(user_id, {}).get(key)
        return self.user_data.get(user_id, {})


class TelegramBot:
    """
    Telegram-бот Мини-Банка.
    При переводе денег — ОТПРАВЛЯЕТ УВЕДОМЛЕНИЕ получателю.
    """

    def __init__(self, db, history, log_cb=None):
        self.bot = telebot.TeleBot(Config.BOT_TOKEN)
        self.db = db
        self.history = history
        self.states = States()
        self.log_callback = log_cb
        self.setup_handlers()

    def log(self, message):
        """Выводит сообщение в консоль и вызывает callback."""
        print(message)
        if self.log_callback:
            self.log_callback(message)

    def create_bottom_keyboard(self):
        """Создаёт клавиатуру с 3 кнопками внизу экрана."""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        keyboard.add(
            types.KeyboardButton("💰 Кошелёк"),
            types.KeyboardButton("📋 История"),
            types.KeyboardButton("👤 Профиль"),
        )
        return keyboard

    def create_inline_keyboard(self, buttons):
        """Создаёт инлайн-клавиатуру из списка кнопок [(текст, callback), ...]."""
        keyboard = types.InlineKeyboardMarkup()
        for button_text, callback_data in buttons:
            keyboard.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
        return keyboard

    # ═══════════════════════════════════════════
    #  ОТПРАВКА УВЕДОМЛЕНИЯ ПОЛУЧАТЕЛЮ
    # ═══════════════════════════════════════════

    def notify_user(self, receiver, sender_name, amount):
        """
        Отправить уведомление получателю в Telegram.
        Работает если у получателя есть telegram_chat_id.
        Возвращает True если уведомление отправлено.
        """
        chat_id = receiver.telegram_chat_id
        if not chat_id:
            self.log(f"⚠️ У {receiver.full_name()} нет Telegram — уведомление не отправлено")
            return False

        try:
            self.bot.send_message(
                chat_id,
                f"💰💰💰💰💰💰💰💰💰💰\n\n"
                f"📥 *Вам перевели деньги!*\n\n"
                f"👤 От кого: *{sender_name}*\n"
                f"💵 Сумма: *+{amount:,.2f} {Config.CURRENCY}*\n"
                f"💰 Ваш баланс: *{receiver.balance:,.2f} {Config.CURRENCY}*\n\n"
                f"💰💰💰💰💰💰💰💰💰💰",
                parse_mode="Markdown",
                reply_markup=self.create_bottom_keyboard(),
            )
            self.log(f"📨 Уведомление отправлено: {receiver.full_name()}")
            return True

        except Exception as error:
            self.log(f"❌ Ошибка уведомления {receiver.full_name()}: {error}")
            return False

    # ═══════════════════════════════════════════
    #  ПОИСК ПОЛЬЗОВАТЕЛЯ ПО TELEGRAM CHAT ID
    # ═══════════════════════════════════════════

    def find_user_by_chat_id(self, chat_id):
        """Найти пользователя по его Telegram chat_id."""
        all_users = self.db._read()
        for user_data in all_users.values():
            if user_data.get("telegram_chat_id") == chat_id:
                return User.from_dict(user_data)
        return None

    # ═══════════════════════════════════════════
    #  ВЫПОЛНЕНИЕ ПЕРЕВОДА + УВЕДОМЛЕНИЕ
    # ═══════════════════════════════════════════

    def execute_transfer(self, chat_id):
        """Выполняет перевод денег между пользователями."""
        transfer_data = self.states.get_data(chat_id)

        # Проверяем что все данные на месте
        if not transfer_data or "amount" not in transfer_data:
            self.bot.send_message(chat_id, "❌ Ошибка.",
                                  reply_markup=self.create_bottom_keyboard())
            self.states.reset(chat_id)
            return

        sender = self.find_user_by_chat_id(chat_id)
        receiver = self.db.get(transfer_data["rcv_id"])
        amount = transfer_data["amount"]

        # Проверяем что отправитель и получатель существуют и хватает денег
        if not sender or not receiver or not sender.has_funds(amount):
            self.bot.send_message(chat_id, "❌ Ошибка перевода.",
                                  reply_markup=self.create_bottom_keyboard())
            self.states.reset(chat_id)
            return

        # ── Списание и зачисление ──
        sender.debit(amount)
        receiver.credit(amount)
        self.db.save(sender)
        self.db.save(receiver)

        # ── Записываем в историю ──
        transaction = Transaction(
            sender.phone, sender.full_name(),
            receiver.phone, receiver.full_name(), amount,
        )
        self.history.add(sender.user_id, transaction.fmt_sender())
        self.history.add(receiver.user_id, transaction.fmt_receiver())

        # ── Уведомляем отправителя ──
        self.bot.send_message(
            chat_id,
            f"✅ *Перевод выполнен!*\n\n"
            f"👤 Получатель: {receiver.full_name()}\n"
            f"💰 Сумма: {amount:,.2f} {Config.CURRENCY}\n"
            f"💵 Остаток: *{sender.balance:,.2f} {Config.CURRENCY}*",
            parse_mode="Markdown",
            reply_markup=self.create_bottom_keyboard(),
        )

        # ── Уведомляем получателя в Telegram ──
        notified = self.notify_user(receiver, sender.full_name(), amount)

        if notified:
            self.log(
                f"💸 Перевод: {sender.full_name()} → "
                f"{receiver.full_name()}: {amount} {Config.CURRENCY} "
                f"(уведомление ✅)"
            )
        else:
            self.log(
                f"💸 Перевод: {sender.full_name()} → "
                f"{receiver.full_name()}: {amount} {Config.CURRENCY} "
                f"(без уведомления)"
            )

        self.states.reset(chat_id)

    # ═══════════════════════════════════════════
    #  РЕГИСТРАЦИЯ ВСЕХ ОБРАБОТЧИКОВ
    # ═══════════════════════════════════════════

    def setup_handlers(self):
        """Регистрирует все обработчики сообщений бота."""
        bot = self.bot

        # ─── Команда /start ───

        @bot.message_handler(commands=["start"])
        def handle_start(message):
            chat_id = message.from_user.id
            self.states.reset(chat_id)

            # Ищем пользователя с привязкой к этому Telegram ID
            found_user = None
            all_users = self.db._read()
            for user_data in all_users.values():
                if user_data.get("telegram_chat_id") == chat_id:
                    found_user = User.from_dict(user_data)
                    break

            if found_user:
                # Пользователь уже зарегистрирован и привязан
                bot.send_message(
                    chat_id,
                    f"👋 С возвращением, *{found_user.full_name()}*!\n\n"
                    f"💰 Баланс: *{found_user.balance:,.2f} {Config.CURRENCY}*\n\n"
                    f"⬇️ Кнопки внизу:",
                    parse_mode="Markdown",
                    reply_markup=self.create_bottom_keyboard(),
                )
                self.log(f"✅ Вход: {found_user.full_name()}")
            else:
                # Новый пользователь — предлагаем регистрацию
                bot.send_message(
                    chat_id,
                    "👋 Добро пожаловать в 🏦 *Мини-Банк*!\n\n"
                    "Зарегистрируйтесь чтобы начать:",
                    parse_mode="Markdown",
                    reply_markup=self.create_inline_keyboard([("📝 Регистрация", "reg")]),
                )

        # ─── Кнопка "Кошелёк" ───

        @bot.message_handler(func=lambda message: message.text == "💰 Кошелёк")
        def handle_wallet(message):
            chat_id = message.from_user.id
            user = self.find_user_by_chat_id(chat_id)

            if not user:
                bot.send_message(chat_id, "⚠️ Нажмите /start")
                return

            self.states.reset(chat_id)
            bot.send_message(
                chat_id,
                f"💰 *Кошелёк*\n\n"
                f"💵 Баланс: *{user.balance:,.2f} {Config.CURRENCY}*",
                parse_mode="Markdown",
                reply_markup=self.create_inline_keyboard([("💸 Перевести деньги", "transfer")]),
            )

        # ─── Кнопка "История" ───

        @bot.message_handler(func=lambda message: message.text == "📋 История")
        def handle_history(message):
            chat_id = message.from_user.id
            user = self.find_user_by_chat_id(chat_id)

            if not user:
                bot.send_message(chat_id, "⚠️ Нажмите /start")
                return

            self.states.reset(chat_id)
            history_text = self.history.get_all(user.user_id)

            # Telegram ограничивает длину сообщения
            if len(history_text) > 4000:
                history_text = history_text[-4000:]

            bot.send_message(
                chat_id,
                f"📋 *История операций*\n\n{history_text}",
                parse_mode="Markdown",
                reply_markup=self.create_bottom_keyboard(),
            )

        # ─── Кнопка "Профиль" ───

        @bot.message_handler(func=lambda message: message.text == "👤 Профиль")
        def handle_profile(message):
            chat_id = message.from_user.id
            user = self.find_user_by_chat_id(chat_id)

            if not user:
                bot.send_message(chat_id, "⚠️ Нажмите /start")
                return

            self.states.reset(chat_id)
            bot.send_message(
                chat_id,
                f"👤 *Профиль*\n\n"
                f"🆔 ID: `{user.user_id}`\n"
                f"👤 Имя: {user.first_name}\n"
                f"👤 Фамилия: {user.last_name}\n"
                f"📱 Телефон: `{user.phone}`\n"
                f"💰 Баланс: *{user.balance:,.2f} {Config.CURRENCY}*\n"
                f"📅 Дата: {user.created_at}",
                parse_mode="Markdown",
                reply_markup=self.create_bottom_keyboard(),
            )

        # ─── Обработка инлайн-кнопок ───

        @bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            chat_id = call.from_user.id
            bot.answer_callback_query(call.id)

            if call.data == "reg":
                # Начинаем регистрацию
                self.states.set(chat_id, St.REG_FIRST)
                bot.send_message(
                    chat_id,
                    "📝 *Регистрация — Шаг 1/4*\n\nВведите ваше *имя*:",
                    parse_mode="Markdown",
                    reply_markup=self.create_inline_keyboard([("❌ Отмена", "cancel")]),
                )

            elif call.data == "transfer":
                # Начинаем перевод
                self.states.set(chat_id, St.TR_PHONE)
                bot.send_message(
                    chat_id,
                    "💸 *Перевод*\n\n"
                    "Введите *номер телефона* получателя:\n"
                    "`+992XXXXXXXXX`",
                    parse_mode="Markdown",
                    reply_markup=self.create_inline_keyboard([("❌ Отмена", "cancel")]),
                )

            elif call.data == "confirm_yes":
                # Подтверждение перевода
                self.execute_transfer(chat_id)

            elif call.data == "cancel" or call.data == "confirm_no":
                # Отмена любого действия
                self.states.reset(chat_id)
                bot.send_message(chat_id, "❌ Отменено.",
                                 reply_markup=self.create_bottom_keyboard())

        # ─── Обработка текстовых сообщений ───

        @bot.message_handler(content_types=["text"])
        def handle_text(message):
            chat_id = message.from_user.id
            text = message.text.strip()
            current_state = self.states.get(chat_id)

            # ════ РЕГИСТРАЦИЯ: ШАГ 1 — ИМЯ ════

            if current_state == St.REG_FIRST:
                if len(text) < 2:
                    bot.send_message(chat_id, "❌ Минимум 2 символа!")
                    return

                self.states.save_data(chat_id, "first", text)
                self.states.set(chat_id, St.REG_LAST)
                bot.send_message(chat_id, "📝 *Шаг 2/4*\nВведите *фамилию*:",
                                 parse_mode="Markdown")

            # ════ РЕГИСТРАЦИЯ: ШАГ 2 — ФАМИЛИЯ ════

            elif current_state == St.REG_LAST:
                if len(text) < 2:
                    bot.send_message(chat_id, "❌ Минимум 2 символа!")
                    return

                self.states.save_data(chat_id, "last", text)
                self.states.set(chat_id, St.REG_PHONE)
                bot.send_message(
                    chat_id,
                    "📝 *Шаг 3/4*\nВведите *телефон*:\n`+992XXXXXXXXX`",
                    parse_mode="Markdown",
                )

            # ════ РЕГИСТРАЦИЯ: ШАГ 3 — ТЕЛЕФОН ════

            elif current_state == St.REG_PHONE:
                phone = text.replace(" ", "").replace("-", "")

                # Проверяем формат номера
                if not (phone.startswith("+") and len(phone) >= 10 and phone[1:].isdigit()):
                    bot.send_message(chat_id, "❌ Формат: +992XXXXXXXXX")
                    return

                # Проверяем занят ли номер
                if self.db.phone_exists(phone):
                    # Может аккаунт создан через GUI — предлагаем привязать Telegram
                    existing_user = self.db.get_by_phone(phone)
                    if existing_user and not existing_user.telegram_chat_id:
                        bot.send_message(
                            chat_id,
                            f"📱 Номер `{phone}` уже зарегистрирован.\n"
                            f"Введите *PIN-код* чтобы привязать Telegram:",
                            parse_mode="Markdown",
                        )
                        self.states.save_data(chat_id, "link_phone", phone)
                        self.states.set(chat_id, St.IDLE)
                        return

                    bot.send_message(chat_id, "❌ Номер уже занят!")
                    return

                self.states.save_data(chat_id, "phone", phone)
                self.states.set(chat_id, St.REG_PIN)
                bot.send_message(
                    chat_id,
                    f"📝 *Шаг 4/4*\nПридумайте *PIN* ({Config.PIN_LENGTH} цифры):",
                    parse_mode="Markdown",
                )

            # ════ РЕГИСТРАЦИЯ: ШАГ 4 — PIN-КОД ════

            elif current_state == St.REG_PIN:
                if not (text.isdigit() and len(text) == Config.PIN_LENGTH):
                    bot.send_message(chat_id, f"❌ PIN = ровно {Config.PIN_LENGTH} цифры!")
                    return

                # Получаем все сохранённые данные регистрации
                reg_data = self.states.get_data(chat_id)
                new_user_id = self.db.gen_id()

                # Создаём нового пользователя
                new_user = User(
                    user_id=new_user_id,
                    phone=reg_data["phone"],
                    first_name=reg_data["first"],
                    last_name=reg_data["last"],
                    pin_code=text,
                    balance=Config.INITIAL_BALANCE,
                    telegram_chat_id=chat_id,
                )
                self.db.save(new_user)
                self.states.reset(chat_id)

                bot.send_message(
                    chat_id,
                    f"🎉 *Регистрация завершена!*\n\n"
                    f"👤 {new_user.full_name()}\n"
                    f"📱 {new_user.phone}\n"
                    f"💰 Баланс: {new_user.balance:,.2f} {Config.CURRENCY}\n\n"
                    f"✅ Telegram привязан — вы будете получать\n"
                    f"уведомления о переводах!\n\n"
                    f"⬇️ Используйте кнопки внизу:",
                    parse_mode="Markdown",
                    reply_markup=self.create_bottom_keyboard(),
                )
                self.log(f"🆕 Регистрация: {new_user.full_name()} (TG привязан)")

            # ════ ПЕРЕВОД: ШАГ 1 — НОМЕР ПОЛУЧАТЕЛЯ ════

            elif current_state == St.TR_PHONE:
                phone = text.replace(" ", "").replace("-", "")

                # Проверяем формат
                if not (phone.startswith("+") and len(phone) >= 10 and phone[1:].isdigit()):
                    bot.send_message(chat_id, "❌ Формат: +992XXXXXXXXX")
                    return

                # Нельзя переводить самому себе
                sender = self.find_user_by_chat_id(chat_id)
                if sender and sender.phone == phone:
                    bot.send_message(chat_id, "❌ Нельзя себе!")
                    return

                # Ищем получателя
                receiver = self.db.get_by_phone(phone)
                if not receiver:
                    bot.send_message(
                        chat_id,
                        "❌ *Нет пользователя с таким номером!*",
                        parse_mode="Markdown",
                        reply_markup=self.create_bottom_keyboard(),
                    )
                    self.states.reset(chat_id)
                    return

                # Сохраняем данные получателя
                self.states.save_data(chat_id, "rcv_id", receiver.user_id)
                self.states.save_data(chat_id, "rcv_name", receiver.full_name())
                self.states.save_data(chat_id, "rcv_phone", phone)
                self.states.set(chat_id, St.TR_AMOUNT)

                # Показываем есть ли у получателя Telegram
                if receiver.telegram_chat_id:
                    telegram_status = "✅ Telegram"
                else:
                    telegram_status = "❌ нет Telegram"

                bot.send_message(
                    chat_id,
                    f"👤 Получатель: *{receiver.full_name()}*\n"
                    f"📱 Уведомление: {telegram_status}\n\n"
                    f"Введите *сумму* ({Config.CURRENCY}):",
                    parse_mode="Markdown",
                )

            # ════ ПЕРЕВОД: ШАГ 2 — СУММА ════

            elif current_state == St.TR_AMOUNT:
                # Проверяем что сумма корректная
                try:
                    amount = round(float(text.replace(",", ".")), 2)
                    assert amount > 0
                except:
                    bot.send_message(chat_id, "❌ Введите число > 0:")
                    return

                # Проверяем хватает ли денег
                sender = self.find_user_by_chat_id(chat_id)
                if not sender.has_funds(amount):
                    bot.send_message(
                        chat_id,
                        f"❌ Недостаточно!\nБаланс: {sender.balance:,.2f}",
                    )
                    return

                # Сохраняем сумму и просим подтверждение
                self.states.save_data(chat_id, "amount", amount)
                self.states.set(chat_id, St.TR_CONFIRM)
                transfer_data = self.states.get_data(chat_id)

                # Создаём клавиатуру с двумя кнопками в ряд
                confirm_keyboard = types.InlineKeyboardMarkup(row_width=2)
                confirm_keyboard.add(
                    types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes"),
                    types.InlineKeyboardButton("❌ Отмена", callback_data="confirm_no"),
                )

                bot.send_message(
                    chat_id,
                    f"💸 *Подтвердите перевод:*\n\n"
                    f"👤 Кому: {transfer_data['rcv_name']}\n"
                    f"📱 Номер: `{transfer_data['rcv_phone']}`\n"
                    f"💰 Сумма: *{amount:,.2f} {Config.CURRENCY}*\n\n"
                    f"Подтвердить?",
                    parse_mode="Markdown",
                    reply_markup=confirm_keyboard,
                )

            # ════ ПЕРЕВОД: ОЖИДАНИЕ ПОДТВЕРЖДЕНИЯ ════

            elif current_state == St.TR_CONFIRM:
                bot.send_message(chat_id, "⬆️ Нажмите кнопку выше.")

            # ════ ОСТАЛЬНЫЕ СООБЩЕНИЯ ════

            else:
                # Проверяем: может пользователь привязывает аккаунт по PIN
                link_phone = self.states.get_data(chat_id, "link_phone")

                if link_phone:
                    # Пользователь вводит PIN для привязки Telegram
                    existing_user = self.db.get_by_phone(link_phone)

                    if existing_user and existing_user.verify_pin(text):
                        # PIN верный — привязываем Telegram
                        existing_user.telegram_chat_id = chat_id
                        self.db.save(existing_user)
                        self.states.reset(chat_id)

                        bot.send_message(
                            chat_id,
                            f"✅ *Telegram привязан!*\n\n"
                            f"👤 {existing_user.full_name()}\n"
                            f"💰 Баланс: {existing_user.balance:,.2f} "
                            f"{Config.CURRENCY}\n\n"
                            f"Теперь вы будете получать уведомления "
                            f"о переводах!",
                            parse_mode="Markdown",
                            reply_markup=self.create_bottom_keyboard(),
                        )
                        self.log(f"🔗 Привязка TG: {existing_user.full_name()}")
                    else:
                        bot.send_message(chat_id, "❌ Неверный PIN!")
                    return

                # Обычное сообщение — показываем подсказку
                user = self.find_user_by_chat_id(chat_id)
                if user:
                    bot.send_message(chat_id, "⬇️ Кнопки внизу:",
                                     reply_markup=self.create_bottom_keyboard())
                else:
                    bot.send_message(chat_id, "Нажмите /start")

    def run(self):
        """Запускает бота."""
        self.log("🤖 Telegram-бот запущен!")
        self.bot.infinity_polling(skip_pending=True)

    def stop(self):
        """Останавливает бота."""
        self.bot.stop_polling()