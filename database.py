import json
import os

from config import Config
from models import User


class UserDatabase:
    """База данных пользователей. Хранит данные в JSON файле."""

    def __init__(self):
        self.path = Config.USERS_FILE
        self.init_storage()
        self.next_id = self.calculate_next_id()

    def init_storage(self):
        """Создаёт пустой JSON файл если его нет."""
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump({}, file)

    def read_all(self):
        """Читает все данные из JSON файла."""
        with open(self.path, "r", encoding="utf-8") as file:
            return json.load(file)

    # Оставляем _read как обёртку, потому что telegram_bot.py вызывает self.db._read()
    def _read(self):
        """Обёртка для обратной совместимости."""
        return self.read_all()

    def write_all(self, data):
        """Записывает все данные в JSON файл."""
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def calculate_next_id(self):
        """Вычисляет следующий свободный ID пользователя."""
        data = self.read_all()
        if not data:
            return 1
        max_id = max(int(key) for key in data)
        return max_id + 1

    def gen_id(self):
        """Генерирует новый уникальный ID."""
        new_id = self.next_id
        self.next_id += 1
        return new_id

    def save(self, user):
        """Сохраняет пользователя в базу данных."""
        data = self.read_all()
        data[str(user.user_id)] = user.to_dict()
        self.write_all(data)

    def get(self, user_id):
        """Получает пользователя по ID. Возвращает None если не найден."""
        data = self.read_all()
        user_data = data.get(str(user_id))
        if user_data:
            return User.from_dict(user_data)
        return None

    def get_by_phone(self, phone):
        """Ищет пользователя по номеру телефона. Возвращает None если не найден."""
        all_users = self.read_all()
        for user_data in all_users.values():
            if user_data["phone"] == phone:
                return User.from_dict(user_data)
        return None

    def phone_exists(self, phone):
        """Проверяет, зарегистрирован ли номер телефона."""
        all_users = self.read_all()
        for user_data in all_users.values():
            if user_data["phone"] == phone:
                return True
        return False

    def authenticate(self, phone, pin):
        """Проверяет логин и пароль. Возвращает пользователя или None."""
        user = self.get_by_phone(phone)
        if user and user.verify_pin(pin):
            return user
        return None

    def count(self):
        """Возвращает количество пользователей в базе."""
        data = self.read_all()
        return len(data)

    def link_telegram(self, phone, chat_id):
        """
        Привязать Telegram chat_id к аккаунту по номеру.
        Вызывается когда пользователь пишет /start боту.
        Возвращает True если привязка успешна.
        """
        data = self.read_all()
        for user_id, user_data in data.items():
            if user_data["phone"] == phone:
                user_data["telegram_chat_id"] = chat_id
                self.write_all(data)
                return True
        return False


class HistoryManager:
    """Менеджер истории операций. Хранит историю в текстовых файлах."""

    def __init__(self):
        self.path = Config.HISTORY_DIR
        self.init_storage()

    def init_storage(self):
        """Создаёт папку для файлов истории если её нет."""
        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def get_file_path(self, user_id):
        """Возвращает путь к файлу истории конкретного пользователя."""
        return os.path.join(self.path, f"{user_id}.txt")

    def add(self, user_id, record):
        """Добавляет запись в историю пользователя."""
        file_path = self.get_file_path(user_id)
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(record + "\n" + "─" * 45 + "\n")

    def get_all(self, user_id):
        """Возвращает всю историю пользователя. Если пусто — возвращает заглушку."""
        file_path = self.get_file_path(user_id)

        # Проверяем существует ли файл
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                history_text = file.read().strip()
                if history_text:
                    return history_text

        return "📭 История пуста."