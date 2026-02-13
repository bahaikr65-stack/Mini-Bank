import telebot
from telebot import types
from enum import Enum, auto
from config import Config
from models import User, Transaction
from database import UserDatabase, HistoryManager


class St(Enum):
    IDLE = auto()
    REG_FIRST = auto()
    REG_LAST = auto()
    REG_PHONE = auto()
    REG_PIN = auto()
    TR_PHONE = auto()
    TR_AMOUNT = auto()
    TR_CONFIRM = auto()


class States:
    def __init__(self):
        self._s = {}
        self._d = {}

    def set(self, uid, st):
        self._s[uid] = st

    def get(self, uid):
        return self._s.get(uid, St.IDLE)

    def reset(self, uid):
        self._s[uid] = St.IDLE
        self._d.pop(uid, None)

    def put(self, uid, k, v):
        self._d.setdefault(uid, {})[k] = v

    def data(self, uid, k=None):
        if k:
            return self._d.get(uid, {}).get(k)
        return self._d.get(uid, {})


class TelegramBot:
    """
    Telegram-бот Мини-Банка.
    При переводе денег — ОТПРАВЛЯЕТ УВЕДОМЛЕНИЕ получателю.
    """

    def __init__(self, db, history, log_cb=None):
        self.bot = telebot.TeleBot(Config.BOT_TOKEN)
        self.db = db
        self.history = history
        self.st = States()
        self._log_cb = log_cb
        self._setup()

    def _log(self, msg):
        print(msg)
        if self._log_cb:
            self._log_cb(msg)

    def _bottom_kb(self):
        m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        m.add(
            types.KeyboardButton("💰 Кошелёк"),
            types.KeyboardButton("📋 История"),
            types.KeyboardButton("👤 Профиль"),
        )
        return m

    def _inline(self, btns):
        kb = types.InlineKeyboardMarkup()
        for text, cb in btns:
            kb.add(types.InlineKeyboardButton(text, callback_data=cb))
        return kb

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
            self._log(f"⚠️ У {receiver.full_name()} нет Telegram — "
                      f"уведомление не отправлено")
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
                reply_markup=self._bottom_kb(),
            )
            self._log(f"📨 Уведомление отправлено: {receiver.full_name()}")
            return True

        except Exception as e:
            self._log(f"❌ Ошибка уведомления {receiver.full_name()}: {e}")
            return False

    # ═══════════════════════════════════════════
    #  РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
    # ═══════════════════════════════════════════

    def _setup(self):
        bot = self.bot

        @bot.message_handler(commands=["start"])
        def start(m):
            uid = m.from_user.id
            self.st.reset(uid)

            # Проверяем есть ли аккаунт с привязкой к этому telegram id
            found = False
            for ud in self.db._read().values():
                if ud.get("telegram_chat_id") == uid:
                    user = User.from_dict(ud)
                    found = True
                    break

            if found:
                bot.send_message(
                    uid,
                    f"👋 С возвращением, *{user.full_name()}*!\n\n"
                    f"💰 Баланс: *{user.balance:,.2f} {Config.CURRENCY}*\n\n"
                    f"⬇️ Кнопки внизу:",
                    parse_mode="Markdown",
                    reply_markup=self._bottom_kb(),
                )
                self._log(f"✅ Вход: {user.full_name()}")
            else:
                bot.send_message(
                    uid,
                    "👋 Добро пожаловать в 🏦 *Мини-Банк*!\n\n"
                    "Зарегистрируйтесь чтобы начать:",
                    parse_mode="Markdown",
                    reply_markup=self._inline([("📝 Регистрация", "reg")]),
                )

        # ─── 3 кнопки внизу ───

        @bot.message_handler(func=lambda m: m.text == "💰 Кошелёк")
        def wallet(m):
            uid = m.from_user.id
            u = self._get_user_by_chat(uid)
            if not u:
                bot.send_message(uid, "⚠️ Нажмите /start")
                return
            self.st.reset(uid)
            bot.send_message(
                uid,
                f"💰 *Кошелёк*\n\n"
                f"💵 Баланс: *{u.balance:,.2f} {Config.CURRENCY}*",
                parse_mode="Markdown",
                reply_markup=self._inline([("💸 Перевести деньги", "transfer")]),
            )

        @bot.message_handler(func=lambda m: m.text == "📋 История")
        def hist(m):
            uid = m.from_user.id
            u = self._get_user_by_chat(uid)
            if not u:
                bot.send_message(uid, "⚠️ Нажмите /start")
                return
            self.st.reset(uid)
            txt = self.history.get_all(u.user_id)
            if len(txt) > 4000:
                txt = txt[-4000:]
            bot.send_message(
                uid,
                f"📋 *История операций*\n\n{txt}",
                parse_mode="Markdown",
                reply_markup=self._bottom_kb(),
            )

        @bot.message_handler(func=lambda m: m.text == "👤 Профиль")
        def prof(m):
            uid = m.from_user.id
            u = self._get_user_by_chat(uid)
            if not u:
                bot.send_message(uid, "⚠️ Нажмите /start")
                return
            self.st.reset(uid)
            bot.send_message(
                uid,
                f"👤 *Профиль*\n\n"
                f"🆔 ID: `{u.user_id}`\n"
                f"👤 Имя: {u.first_name}\n"
                f"👤 Фамилия: {u.last_name}\n"
                f"📱 Телефон: `{u.phone}`\n"
                f"💰 Баланс: *{u.balance:,.2f} {Config.CURRENCY}*\n"
                f"📅 Дата: {u.created_at}",
                parse_mode="Markdown",
                reply_markup=self._bottom_kb(),
            )

        # ─── Callback ───

        @bot.callback_query_handler(func=lambda c: True)
        def cb(call):
            uid = call.from_user.id
            bot.answer_callback_query(call.id)

            if call.data == "reg":
                self.st.set(uid, St.REG_FIRST)
                bot.send_message(
                    uid,
                    "📝 *Регистрация — Шаг 1/4*\n\nВведите ваше *имя*:",
                    parse_mode="Markdown",
                    reply_markup=self._inline([("❌ Отмена", "cancel")]),
                )

            elif call.data == "transfer":
                self.st.set(uid, St.TR_PHONE)
                bot.send_message(
                    uid,
                    "💸 *Перевод*\n\n"
                    "Введите *номер телефона* получателя:\n"
                    "`+992XXXXXXXXX`",
                    parse_mode="Markdown",
                    reply_markup=self._inline([("❌ Отмена", "cancel")]),
                )

            elif call.data == "confirm_yes":
                self._do_transfer(uid)

            elif call.data in ("cancel", "confirm_no"):
                self.st.reset(uid)
                bot.send_message(uid, "❌ Отменено.",
                                 reply_markup=self._bottom_kb())

        # ─── Текст ───

        @bot.message_handler(content_types=["text"])
        def txt(m):
            uid = m.from_user.id
            t = m.text.strip()
            s = self.st.get(uid)

            if s == St.REG_FIRST:
                if len(t) < 2:
                    bot.send_message(uid, "❌ Минимум 2 символа!")
                    return
                self.st.put(uid, "first", t)
                self.st.set(uid, St.REG_LAST)
                bot.send_message(uid, "📝 *Шаг 2/4*\nВведите *фамилию*:",
                                 parse_mode="Markdown")

            elif s == St.REG_LAST:
                if len(t) < 2:
                    bot.send_message(uid, "❌ Минимум 2 символа!")
                    return
                self.st.put(uid, "last", t)
                self.st.set(uid, St.REG_PHONE)
                bot.send_message(
                    uid,
                    "📝 *Шаг 3/4*\nВведите *телефон*:\n`+992XXXXXXXXX`",
                    parse_mode="Markdown",
                )

            elif s == St.REG_PHONE:
                ph = t.replace(" ", "").replace("-", "")
                if not (ph.startswith("+") and len(ph) >= 10
                        and ph[1:].isdigit()):
                    bot.send_message(uid, "❌ Формат: +992XXXXXXXXX")
                    return
                if self.db.phone_exists(ph):
                    # Может аккаунт создан через GUI — привяжем Telegram
                    existing = self.db.get_by_phone(ph)
                    if existing and not existing.telegram_chat_id:
                        bot.send_message(
                            uid,
                            f"📱 Номер `{ph}` уже зарегистрирован.\n"
                            f"Введите *PIN-код* чтобы привязать Telegram:",
                            parse_mode="Markdown",
                        )
                        self.st.put(uid, "link_phone", ph)
                        self.st.set(uid, St.IDLE)  # отдельный обработчик
                        return
                    bot.send_message(uid, "❌ Номер уже занят!")
                    return
                self.st.put(uid, "phone", ph)
                self.st.set(uid, St.REG_PIN)
                bot.send_message(
                    uid,
                    f"📝 *Шаг 4/4*\nПридумайте *PIN* ({Config.PIN_LENGTH} цифры):",
                    parse_mode="Markdown",
                )

            elif s == St.REG_PIN:
                if not (t.isdigit() and len(t) == Config.PIN_LENGTH):
                    bot.send_message(
                        uid, f"❌ PIN = ровно {Config.PIN_LENGTH} цифры!")
                    return
                d = self.st.data(uid)
                new_id = self.db.gen_id()
                user = User(
                    user_id=new_id,
                    phone=d["phone"],
                    first_name=d["first"],
                    last_name=d["last"],
                    pin_code=t,
                    balance=Config.INITIAL_BALANCE,
                    telegram_chat_id=uid,  # ← ПРИВЯЗЫВАЕМ TELEGRAM
                )
                self.db.save(user)
                self.st.reset(uid)

                bot.send_message(
                    uid,
                    f"🎉 *Регистрация завершена!*\n\n"
                    f"👤 {user.full_name()}\n"
                    f"📱 {user.phone}\n"
                    f"💰 Баланс: {user.balance:,.2f} {Config.CURRENCY}\n\n"
                    f"✅ Telegram привязан — вы будете получать\n"
                    f"уведомления о переводах!\n\n"
                    f"⬇️ Используйте кнопки внизу:",
                    parse_mode="Markdown",
                    reply_markup=self._bottom_kb(),
                )
                self._log(f"🆕 Регистрация: {user.full_name()} (TG привязан)")

            # ─── Перевод ───

            elif s == St.TR_PHONE:
                ph = t.replace(" ", "").replace("-", "")
                if not (ph.startswith("+") and len(ph) >= 10
                        and ph[1:].isdigit()):
                    bot.send_message(uid, "❌ Формат: +992XXXXXXXXX")
                    return

                sender = self._get_user_by_chat(uid)
                if sender and sender.phone == ph:
                    bot.send_message(uid, "❌ Нельзя себе!")
                    return

                rcv = self.db.get_by_phone(ph)
                if not rcv:
                    bot.send_message(
                        uid,
                        "❌ *Нет пользователя с таким номером!*",
                        parse_mode="Markdown",
                        reply_markup=self._bottom_kb(),
                    )
                    self.st.reset(uid)
                    return

                self.st.put(uid, "rcv_id", rcv.user_id)
                self.st.put(uid, "rcv_name", rcv.full_name())
                self.st.put(uid, "rcv_phone", ph)
                self.st.set(uid, St.TR_AMOUNT)

                has_tg = "✅ Telegram" if rcv.telegram_chat_id else "❌ нет Telegram"
                bot.send_message(
                    uid,
                    f"👤 Получатель: *{rcv.full_name()}*\n"
                    f"📱 Уведомление: {has_tg}\n\n"
                    f"Введите *сумму* ({Config.CURRENCY}):",
                    parse_mode="Markdown",
                )

            elif s == St.TR_AMOUNT:
                try:
                    amt = round(float(t.replace(",", ".")), 2)
                    assert amt > 0
                except:
                    bot.send_message(uid, "❌ Введите число > 0:")
                    return

                sender = self._get_user_by_chat(uid)
                if not sender.has_funds(amt):
                    bot.send_message(
                        uid,
                        f"❌ Недостаточно!\n"
                        f"Баланс: {sender.balance:,.2f}",
                    )
                    return

                self.st.put(uid, "amount", amt)
                self.st.set(uid, St.TR_CONFIRM)
                d = self.st.data(uid)

                kb = types.InlineKeyboardMarkup(row_width=2)
                kb.add(
                    types.InlineKeyboardButton("✅ Подтвердить",
                                               callback_data="confirm_yes"),
                    types.InlineKeyboardButton("❌ Отмена",
                                               callback_data="confirm_no"),
                )
                bot.send_message(
                    uid,
                    f"💸 *Подтвердите перевод:*\n\n"
                    f"👤 Кому: {d['rcv_name']}\n"
                    f"📱 Номер: `{d['rcv_phone']}`\n"
                    f"💰 Сумма: *{amt:,.2f} {Config.CURRENCY}*\n\n"
                    f"Подтвердить?",
                    parse_mode="Markdown",
                    reply_markup=kb,
                )

            elif s == St.TR_CONFIRM:
                bot.send_message(uid, "⬆️ Нажмите кнопку выше.")

            else:
                # Проверяем привязку аккаунта
                link_phone = self.st.data(uid, "link_phone")
                if link_phone:
                    # Пользователь вводит PIN для привязки
                    existing = self.db.get_by_phone(link_phone)
                    if existing and existing.verify_pin(t):
                        existing.telegram_chat_id = uid
                        self.db.save(existing)
                        self.st.reset(uid)
                        bot.send_message(
                            uid,
                            f"✅ *Telegram привязан!*\n\n"
                            f"👤 {existing.full_name()}\n"
                            f"💰 Баланс: {existing.balance:,.2f} "
                            f"{Config.CURRENCY}\n\n"
                            f"Теперь вы будете получать уведомления "
                            f"о переводах!",
                            parse_mode="Markdown",
                            reply_markup=self._bottom_kb(),
                        )
                        self._log(f"🔗 Привязка TG: {existing.full_name()}")
                    else:
                        bot.send_message(uid, "❌ Неверный PIN!")
                    return

                u = self._get_user_by_chat(uid)
                if u:
                    bot.send_message(uid, "⬇️ Кнопки внизу:",
                                     reply_markup=self._bottom_kb())
                else:
                    bot.send_message(uid, "Нажмите /start")

    # ═══════════════════════════════════════════
    #  ВЫПОЛНЕНИЕ ПЕРЕВОДА + УВЕДОМЛЕНИЕ
    # ═══════════════════════════════════════════

    def _do_transfer(self, chat_id):
        d = self.st.data(chat_id)
        if not d or "amount" not in d:
            self.bot.send_message(chat_id, "❌ Ошибка.",
                                  reply_markup=self._bottom_kb())
            self.st.reset(chat_id)
            return

        sender = self._get_user_by_chat(chat_id)
        rcv = self.db.get(d["rcv_id"])
        amt = d["amount"]

        if not sender or not rcv or not sender.has_funds(amt):
            self.bot.send_message(chat_id, "❌ Ошибка перевода.",
                                  reply_markup=self._bottom_kb())
            self.st.reset(chat_id)
            return

        # ── Списание / зачисление ──
        sender.debit(amt)
        rcv.credit(amt)
        self.db.save(sender)
        self.db.save(rcv)

        # ── История ──
        txn = Transaction(
            sender.phone, sender.full_name(),
            rcv.phone, rcv.full_name(), amt,
        )
        self.history.add(sender.user_id, txn.fmt_sender())
        self.history.add(rcv.user_id, txn.fmt_receiver())

        # ── Уведомляем ОТПРАВИТЕЛЯ ──
        self.bot.send_message(
            chat_id,
            f"✅ *Перевод выполнен!*\n\n"
            f"👤 Получатель: {rcv.full_name()}\n"
            f"💰 Сумма: {amt:,.2f} {Config.CURRENCY}\n"
            f"💵 Остаток: *{sender.balance:,.2f} {Config.CURRENCY}*",
            parse_mode="Markdown",
            reply_markup=self._bottom_kb(),
        )

        # ══════════════════════════════════════
        #  УВЕДОМЛЯЕМ ПОЛУЧАТЕЛЯ В TELEGRAM!
        # ══════════════════════════════════════
        notified = self.notify_user(rcv, sender.full_name(), amt)

        if notified:
            self._log(
                f"💸 Перевод: {sender.full_name()} → "
                f"{rcv.full_name()}: {amt} {Config.CURRENCY} "
                f"(уведомление ✅)"
            )
        else:
            self._log(
                f"💸 Перевод: {sender.full_name()} → "
                f"{rcv.full_name()}: {amt} {Config.CURRENCY} "
                f"(без уведомления)"
            )

        self.st.reset(chat_id)

    # ═══════════════════════════════════════════
    #  ПОИСК ПОЛЬЗОВАТЕЛЯ ПО TELEGRAM CHAT ID
    # ═══════════════════════════════════════════

    def _get_user_by_chat(self, chat_id):
        """Найти пользователя по его Telegram chat_id"""
        for ud in self.db._read().values():
            if ud.get("telegram_chat_id") == chat_id:
                return User.from_dict(ud)
        return None

    def run(self):
        self._log("🤖 Telegram-бот запущен!")
        self.bot.infinity_polling(skip_pending=True)

    def stop(self):
        self.bot.stop_polling()