from abc import ABC, abstractmethod
from datetime import datetime


class BaseModel(ABC):
    def __init__(self):
        self._created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def created_at(self):
        return self._created_at

    @created_at.setter
    def created_at(self, val):
        self._created_at = val

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict):
        pass

    @abstractmethod
    def __str__(self):
        pass


class User(BaseModel):
    def __init__(self, user_id, phone, first_name, last_name,
                 pin_code, balance=0.0, telegram_id=None):
        super().__init__()
        self.user_id = user_id
        self.phone = phone
        self.first_name = first_name
        self.last_name = last_name
        self.__pin_code = pin_code
        self.__balance = balance
        self.telegram_id = telegram_id  # Настоящий Telegram ID пользователя

    @property
    def balance(self):
        return self.__balance

    @balance.setter
    def balance(self, val):
        if val < 0:
            raise ValueError("Баланс < 0")
        self.__balance = val

    @property
    def pin_code(self):
        return self.__pin_code

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def has_funds(self, amount):
        return self.__balance >= amount

    def debit(self, amount):
        if amount <= 0 or not self.has_funds(amount):
            return False
        self.__balance -= amount
        return True

    def credit(self, amount):
        if amount <= 0:
            return False
        self.__balance += amount
        return True

    def verify_pin(self, pin):
        return self.__pin_code == pin

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "pin_code": self.__pin_code,
            "balance": self.__balance,
            "created_at": self.created_at,
            "telegram_id": self.telegram_id,  # Добавлено поле
        }

    @classmethod
    def from_dict(cls, data):
        u = cls(
            user_id=data["user_id"], phone=data["phone"],
            first_name=data["first_name"], last_name=data["last_name"],
            pin_code=data["pin_code"], balance=data["balance"],
            telegram_id=data.get("telegram_id"),  # Добавлено поле
        )
        u.created_at = data.get("created_at", "")
        return u

    def __str__(self):
        return f"User({self.full_name()}, {self.phone})"


class Transaction(BaseModel):
    def __init__(self, sender_phone, sender_name, receiver_phone,
                 receiver_name, amount, timestamp=None):
        super().__init__()
        self.sender_phone = sender_phone
        self.sender_name = sender_name
        self.receiver_phone = receiver_phone
        self.receiver_name = receiver_name
        self.amount = amount
        if timestamp:
            self.created_at = timestamp

    def fmt_sender(self):
        return (f"[{self.created_at}] ОТПРАВЛЕНО\n"
                f"  -{self.amount:.2f} сомони → "
                f"{self.receiver_name} ({self.receiver_phone})")

    def fmt_receiver(self):
        return (f"[{self.created_at}] ПОЛУЧЕНО\n"
                f"  +{self.amount:.2f} сомони ← "
                f"{self.sender_name} ({self.sender_phone})")

    def to_dict(self):
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
        return cls(**data)

    def __str__(self):
        return f"Txn({self.sender_phone}→{self.receiver_phone}:{self.amount})"