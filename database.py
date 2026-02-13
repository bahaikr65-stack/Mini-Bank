import json
import os
from abc import ABC, abstractmethod
from config import Config
from models import User


class BaseStorage(ABC):
    def __init__(self, path):
        self._path = path
        self._init_storage()

    @abstractmethod
    def _init_storage(self):
        pass


class UserDatabase(BaseStorage):
    def __init__(self):
        super().__init__(Config.USERS_FILE)
        self.__next_id = self._calc_next_id()

    def _init_storage(self):
        if not os.path.exists(self._path):
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _read(self):
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def _calc_next_id(self):
        data = self._read()
        return max((int(k) for k in data), default=0) + 1

    def gen_id(self):
        uid = self.__next_id
        self.__next_id += 1
        return uid

    def save(self, user):
        data = self._read()
        data[str(user.user_id)] = user.to_dict()
        self._write(data)

    def get(self, user_id):
        data = self._read()
        ud = data.get(str(user_id))
        return User.from_dict(ud) if ud else None

    def get_by_phone(self, phone):
        for ud in self._read().values():
            if ud["phone"] == phone:
                return User.from_dict(ud)
        return None

    def phone_exists(self, phone):
        return any(u["phone"] == phone for u in self._read().values())

    def authenticate(self, phone, pin):
        user = self.get_by_phone(phone)
        if user and user.verify_pin(pin):
            return user
        return None

    def count(self):
        return len(self._read())

    def link_telegram(self, phone, chat_id):
        """
        Привязать Telegram chat_id к аккаунту по номеру.
        Вызывается когда пользователь пишет /start боту.
        """
        data = self._read()
        for uid, ud in data.items():
            if ud["phone"] == phone:
                ud["telegram_chat_id"] = chat_id
                self._write(data)
                return True
        return False


class HistoryManager(BaseStorage):
    def __init__(self):
        super().__init__(Config.HISTORY_DIR)

    def _init_storage(self):
        if not os.path.exists(self._path):
            os.makedirs(self._path)

    def _file(self, uid):
        return os.path.join(self._path, f"{uid}.txt")

    def add(self, uid, record):
        with open(self._file(uid), "a", encoding="utf-8") as f:
            f.write(record + "\n" + "─" * 45 + "\n")

    def get_all(self, uid):
        fp = self._file(uid)
        if os.path.exists(fp):
            with open(fp, "r", encoding="utf-8") as f:
                txt = f.read().strip()
                if txt:
                    return txt
        return "📭 История пуста."