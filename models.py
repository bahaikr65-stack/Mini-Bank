from datetime import datetime


class User:
    """
    Модель пользователя банка.

    telegram_chat_id — ID чата в Telegram.
    Заполняется при регистрации через бот.
    Через него бот отправляет уведомления.
    """

    def __init__(self, user_id, phone, first_name, last_name,
                 pin_code, balance=0.0, telegram_chat_id=None):
        self.user_id = user_id                    # уникальный ID пользователя
        self.phone = phone                        # номер телефона
        self.first_name = first_name              # имя
        self.last_name = last_name                # фамилия
        self.__pin_code = pin_code                # PIN-код (приватный)
        self.__balance = balance                  # баланс (приватный)
        self.telegram_chat_id = telegram_chat_id  # ID чата в Telegram
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # дата создания

    @property
    def balance(self):
        """Получить текущий баланс."""
        return self.__balance

    @balance.setter
    def balance(self, value):
        """Установить баланс (не может быть меньше нуля)."""
        if value < 0:
            raise ValueError("Баланс < 0")
        self.__balance = value

    @property
    def pin_code(self):
        """Получить PIN-код."""
        return self.__pin_code

    def full_name(self):
        """Возвращает полное имя пользователя."""
        return f"{self.first_name} {self.last_name}"

    def has_funds(self, amount):
        """Проверяет, хватает ли денег на балансе."""
        return self.__balance >= amount

    def debit(self, amount):
        """Списывает деньги с баланса. Возвращает True если успешно."""
        if amount <= 0 or not self.has_funds(amount):
            return False
        self.__balance -= amount
        return True

    def credit(self, amount):
        """Зачисляет деньги на баланс. Возвращает True если успешно."""
        if amount <= 0:
            return False
        self.__balance += amount
        return True

    def verify_pin(self, pin):
        """Проверяет правильность PIN-кода."""
        return self.__pin_code == pin

    def to_dict(self):
        """Преобразует пользователя в словарь для сохранения в JSON."""
        return {
            "user_id": self.user_id,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "pin_code": self.__pin_code,
            "balance": self.__balance,
            "telegram_chat_id": self.telegram_chat_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        """Создаёт пользователя из словаря (загрузка из JSON)."""
        user = cls(
            user_id=data["user_id"],
            phone=data["phone"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            pin_code=data["pin_code"],
            balance=data["balance"],
            telegram_chat_id=data.get("telegram_chat_id"),
        )
        user.created_at = data.get("created_at", "")
        return user

    def __str__(self):
        return f"User({self.full_name()}, {self.phone})"


class Transaction:
    """Модель транзакции (перевод денег между пользователями)."""

    def __init__(self, sender_phone, sender_name,
                 receiver_phone, receiver_name, amount, timestamp=None):
        self.sender_phone = sender_phone      # телефон отправителя
        self.sender_name = sender_name        # имя отправителя
        self.receiver_phone = receiver_phone  # телефон получателя
        self.receiver_name = receiver_name    # имя получателя
        self.amount = amount                  # сумма перевода
        # дата транзакции (если не указана — берём текущую)
        if timestamp:
            self.created_at = timestamp
        else:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def fmt_sender(self):
        """Форматирует запись для истории отправителя."""
        return (
            f"📤 [{self.created_at}] ОТПРАВЛЕНО\n"
            f"   -{self.amount:.2f} сомони\n"
            f"   Кому: {self.receiver_name} ({self.receiver_phone})"
        )

    def fmt_receiver(self):
        """Форматирует запись для истории получателя."""
        return (
            f"📥 [{self.created_at}] ПОЛУЧЕНО\n"
            f"   +{self.amount:.2f} сомони\n"
            f"   От: {self.sender_name} ({self.sender_phone})"
        )

    def to_dict(self):
        """Преобразует транзакцию в словарь для сохранения."""
        return {
            "sender_phone": self.sender_phone,
            "sender_name": self.sender_name,
            "receiver_phone": self.receiver_phone,
            "receiver_name": self.receiver_name,
            "amount": self.amount,
            "timestamp": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        """Создаёт транзакцию из словаря."""
        return cls(
            sender_phone=data["sender_phone"],
            sender_name=data["sender_name"],
            receiver_phone=data["receiver_phone"],
            receiver_name=data["receiver_name"],
            amount=data["amount"],
            timestamp=data.get("timestamp"),
        )

    def __str__(self):
        return f"Transaction({self.sender_phone} → {self.receiver_phone}: {self.amount})"