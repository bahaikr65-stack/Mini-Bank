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

    def _setup(self):
        bot = self.bot

        @bot.message_handler(commands=["start"])
        def start(m):
            uid = m.from_user.id
            self.st.reset(uid)
            if self.db.get(uid):
                u = self.db.get(uid)
                bot.send_message(uid,
                    f"👋 С возвращением, *{u.full_name()}*!\n"
                    f"⬇️ Используйте кнопки внизу:",
                    parse_mode="Markdown",
                    reply_markup=self._bottom_kb())
                self._log(f"Вход: {u.full_name()}")
            else:
                bot.send_message(uid,
                    "👋 Добро пожаловать в 🏦 *Мини-Банк*!\n"
                    "Зарегистрируйтесь:",
                    parse_mode="Markdown",
                    reply_markup=self._inline([("📝 Регистрация", "reg")]))

        @bot.message_handler(func=lambda m: m.text == "💰 Кошелёк")
        def wallet(m):
            uid = m.from_user.id
            u = self.db.get(uid)
            if not u:
                bot.send_message(uid, "Нажмите /start")
                return
            self.st.reset(uid)
            bot.send_message(uid,
                f"💰 *Кошелёк*\n\n"
                f"💵 Баланс: *{u.balance:,.2f} {Config.CURRENCY}*",
                parse_mode="Markdown",
                reply_markup=self._inline([("💸 Перевести", "transfer")]))

        @bot.message_handler(func=lambda m: m.text == "📋 История")
        def hist(m):
            uid = m.from_user.id
            u = self.db.get(uid)
            if not u:
                bot.send_message(uid, "Нажмите /start")
                return
            self.st.reset(uid)
            txt = self.history.get_all(uid)
            if len(txt) > 4000:
                txt = txt[-4000:]
            bot.send_message(uid,
                f"📋 *История*\n\n{txt}",
                parse_mode="Markdown",
                reply_markup=self._bottom_kb())

        @bot.message_handler(func=lambda m: m.text == "👤 Профиль")
        def prof(m):
            uid = m.from_user.id
            u = self.db.get(uid)
            if not u:
                bot.send_message(uid, "Нажмите /start")
                return
            self.st.reset(uid)
            bot.send_message(uid,
                f"👤 *Профиль*\n\n"
                f"🆔 ID: `{u.user_id}`\n"
                f"👤 Имя: {u.first_name}\n"
                f"👤 Фамилия: {u.last_name}\n"
                f"📱 Телефон: `{u.phone}`\n"
                f"💰 Баланс: *{u.balance:,.2f} {Config.CURRENCY}*\n"
                f"📅 Дата: {u.created_at}",
                parse_mode="Markdown",
                reply_markup=self._bottom_kb())

        @bot.callback_query_handler(func=lambda c: True)
        def cb(call):
            uid = call.from_user.id
            bot.answer_callback_query(call.id)

            if call.data == "reg":
                self.st.set(uid, St.REG_FIRST)
                bot.send_message(uid, "📝 *Шаг 1/4*\nВведите *имя*:",
                    parse_mode="Markdown",
                    reply_markup=self._inline([("❌ Отмена", "cancel")]))

            elif call.data == "transfer":
                self.st.set(uid, St.TR_PHONE)
                bot.send_message(uid,
                    "💸 Введите *номер получателя*:\n`+992XXXXXXXXX`",
                    parse_mode="Markdown",
                    reply_markup=self._inline([("❌ Отмена", "cancel")]))

            elif call.data == "confirm_yes":
                self._do_transfer(uid)

            elif call.data in ("cancel", "confirm_no"):
                self.st.reset(uid)
                bot.send_message(uid, "❌ Отменено.",
                    reply_markup=self._bottom_kb())

        @bot.message_handler(content_types=["text"])
        def txt(m):
            uid = m.from_user.id
            t = m.text.strip()
            s = self.st.get(uid)

            if s == St.REG_FIRST:
                if len(t) < 2:
                    bot.send_message(uid, "❌ Минимум 2 символа:")
                    return
                self.st.put(uid, "first", t)
                self.st.set(uid, St.REG_LAST)
                bot.send_message(uid, "📝 *Шаг 2/4*\nВведите *фамилию*:",
                    parse_mode="Markdown")

            elif s == St.REG_LAST:
                if len(t) < 2:
                    bot.send_message(uid, "❌ Минимум 2 символа:")
                    return
                self.st.put(uid, "last", t)
                self.st.set(uid, St.REG_PHONE)
                bot.send_message(uid,
                    "📝 *Шаг 3/4*\nВведите *телефон*:\n`+992XXXXXXXXX`",
                    parse_mode="Markdown")

            elif s == St.REG_PHONE:
                ph = t.replace(" ", "").replace("-", "")
                if not (ph.startswith("+") and len(ph) >= 10 and ph[1:].isdigit()):
                    bot.send_message(uid, "❌ Формат: +992XXXXXXXXX")
                    return
                if self.db.phone_exists(ph):
                    bot.send_message(uid, "❌ Номер занят!")
                    return
                self.st.put(uid, "phone", ph)
                self.st.set(uid, St.REG_PIN)
                bot.send_message(uid,
                    f"📝 *Шаг 4/4*\nПридумайте *PIN* ({Config.PIN_LENGTH} цифры):",
                    parse_mode="Markdown")

            elif s == St.REG_PIN:
                if not (t.isdigit() and len(t) == Config.PIN_LENGTH):
                    bot.send_message(uid, f"❌ PIN = {Config.PIN_LENGTH} цифры!")
                    return
                d = self.st.data(uid)
                # ИСПРАВЛЕНО: передаём настоящий Telegram ID
                user = User(uid, d["phone"], d["first"], d["last"],
                            t, Config.INITIAL_BALANCE, telegram_id=uid)
                self.db.save(user)
                self.st.reset(uid)
                bot.send_message(uid,
                    f"🎉 *Готово!*\n\n"
                    f"👤 {user.full_name()}\n"
                    f"📱 {user.phone}\n"
                    f"💰 {user.balance:,.2f} {Config.CURRENCY}\n\n"
                    f"⬇️ Используйте кнопки:",
                    parse_mode="Markdown",
                    reply_markup=self._bottom_kb())
                self._log(f"🆕 Регистрация (TG): {user.full_name()}")

            elif s == St.TR_PHONE:
                ph = t.replace(" ", "").replace("-", "")
                if not (ph.startswith("+") and len(ph) >= 10 and ph[1:].isdigit()):
                    bot.send_message(uid, "❌ Формат: +992XXXXXXXXX")
                    return
                sender = self.db.get(uid)
                if sender and sender.phone == ph:
                    bot.send_message(uid, "❌ Нельзя себе!")
                    return
                rcv = self.db.get_by_phone(ph)
                if not rcv:
                    bot.send_message(uid,
                        "❌ *Нет пользователя с таким номером!*",
                        parse_mode="Markdown",
                        reply_markup=self._bottom_kb())
                    self.st.reset(uid)
                    return
                self.st.put(uid, "rcv_phone", ph)
                self.st.put(uid, "rcv_id", rcv.user_id)
                self.st.put(uid, "rcv_telegram_id", rcv.telegram_id)  # ИСПРАВЛЕНО: сохраняем Telegram ID
                self.st.put(uid, "rcv_name", rcv.full_name())
                self.st.set(uid, St.TR_AMOUNT)
                bot.send_message(uid,
                    f"👤 Получатель: *{rcv.full_name()}*\n"
                    f"Введите *сумму* ({Config.CURRENCY}):",
                    parse_mode="Markdown")

            elif s == St.TR_AMOUNT:
                try:
                    amt = round(float(t.replace(",", ".")), 2)
                    assert amt > 0
                except:
                    bot.send_message(uid, "❌ Введите число > 0:")
                    return
                sender = self.db.get(uid)
                if not sender.has_funds(amt):
                    bot.send_message(uid,
                        f"❌ Недостаточно! Баланс: {sender.balance:,.2f}")
                    return
                self.st.put(uid, "amount", amt)
                self.st.set(uid, St.TR_CONFIRM)
                d = self.st.data(uid)
                kb = types.InlineKeyboardMarkup(row_width=2)
                kb.add(
                    types.InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
                    types.InlineKeyboardButton("❌ Нет", callback_data="confirm_no"),
                )
                bot.send_message(uid,
                    f"💸 *Подтвердите:*\n\n"
                    f"👤 Кому: {d['rcv_name']}\n"
                    f"💰 Сумма: *{amt:,.2f} {Config.CURRENCY}*",
                    parse_mode="Markdown", reply_markup=kb)
            else:
                if self.db.get(uid):
                    bot.send_message(uid, "⬇️ Кнопки внизу:",
                        reply_markup=self._bottom_kb())
                else:
                    bot.send_message(uid, "Нажмите /start")

    def _do_transfer(self, uid):
        d = self.st.data(uid)
        if not d or "amount" not in d:
            self.bot.send_message(uid, "❌ Ошибка.",
                reply_markup=self._bottom_kb())
            self.st.reset(uid)
            return

        sender = self.db.get(uid)
        rcv = self.db.get(d["rcv_id"])
        amt = d["amount"]

        if not sender or not rcv or not sender.has_funds(amt):
            self.bot.send_message(uid, "❌ Ошибка перевода.",
                reply_markup=self._bottom_kb())
            self.st.reset(uid)
            return

        sender.debit(amt)
        rcv.credit(amt)
        self.db.save(sender)
        self.db.save(rcv)

        txn = Transaction(sender.phone, sender.full_name(),
                          rcv.phone, rcv.full_name(), amt)
        self.history.add(sender.user_id, txn.fmt_sender())
        self.history.add(rcv.user_id, txn.fmt_receiver())

        self.bot.send_message(uid,
            f"✅ *Переведено!*\n\n"
            f"👤 {rcv.full_name()}\n"
            f"💰 {amt:,.2f} {Config.CURRENCY}\n"
            f"💵 Остаток: *{sender.balance:,.2f} {Config.CURRENCY}*",
            parse_mode="Markdown",
            reply_markup=self._bottom_kb())

        # ИСПРАВЛЕНО: отправляем уведомление получателю по его Telegram ID
        if rcv.telegram_id:
            try:
                self.bot.send_message(rcv.telegram_id,
                    f"📥 *Входящий перевод!*\n\n"
                    f"👤 От: {sender.full_name()}\n"
                    f"💰 +{amt:,.2f} {Config.CURRENCY}\n"
                    f"💵 Баланс: *{rcv.balance:,.2f} {Config.CURRENCY}*",
                    parse_mode="Markdown",
                    reply_markup=self._bottom_kb())
                self._log(f"Уведомление отправлено получателю {rcv.full_name()}")
            except Exception as e:
                self._log(f"Ошибка отправки уведомления получателю: {e}")
        else:
            self._log(f"Получатель {rcv.full_name()} не имеет Telegram ID (зарегистрирован в GUI)")

        self._log(f"💸 {sender.full_name()} → {rcv.full_name()}: {amt}")
        self.st.reset(uid)

    def run(self):
        self._log("🤖 Telegram-бот запущен!")
        self.bot.infinity_polling(skip_pending=True)

    def stop(self):
        self.bot.stop_polling()