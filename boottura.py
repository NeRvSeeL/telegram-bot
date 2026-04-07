import logging
from typing import Dict, List, Optional
import os
import asyncio
import aiosqlite
import socks
from aiogram import Bot, Dispatcher, types  # Исправлено здесь
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, PhotoSize, InputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot, Dispatcher
from aiogram.contrib.middlewares.proxy import ProxyMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен вашего бота
BOT_TOKEN = "8226384656:AAHFvXTepxroGm5knawehCYeX5JgbglTzyM"

# Ссылка на аккаунт поддержки
SUPPORT_USERNAME = "WorldAple"

# Путь к папке с изображениями
IMAGES_BASE_PATH = r"C:\Users\NERV\Desktop\код\World Apple\Айфон"

# ID приватного канала для хранения фото
STORAGE_CHANNEL_ID = -1003476302624  # ЗАМЕНИТЕ ЭТО НА ВАШ ID!

# ID администратора (ваш Telegram ID)
ADMIN_ID = 8079478130  # ЗАМЕНИТЕ НА ВАШ ID!

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для отслеживания выбора
class UserState(StatesGroup):
    viewing_product = State()

# База данных для хранения file_id
class PhotoDatabase:
    def __init__(self, db_path: str = "photos.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализирует базу данных"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                model TEXT NOT NULL,
                memory TEXT NOT NULL,
                color_index INTEGER NOT NULL,
                color_name TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_unique_id TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (model, memory, color_index)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
    
    async def get_file_id(self, model: str, memory: str, color_index: int) -> Optional[str]:
        """Получает file_id из базы"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT file_id FROM photos WHERE model = ? AND memory = ? AND color_index = ?",
                (model, memory, color_index)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None
    
    async def save_file_id(self, model: str, memory: str, color_index: int, 
                          color_name: str, photo: PhotoSize):
        """Сохраняет file_id в базу"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO photos 
                (model, memory, color_index, color_name, file_id, file_unique_id, width, height, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                model, memory, color_index, color_name,
                photo.file_id, photo.file_unique_id,
                photo.width, photo.height, photo.file_size
            ))
            await db.commit()
            logger.info(f"✅ Сохранен file_id для {model} {memory} цвет {color_index}")
    
    async def get_cached_count(self):
        """Возвращает количество закэшированных фото"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM photos") as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

# Инициализируем базу данных
db = PhotoDatabase()

# Модели iPhone с реальными ценами (оставляем без изменений)
PRODUCTS = {
    "iPhone 12 mini": {
        "description": "Компактный iPhone 12 mini с дисплеем Super Retina XDR.",
        "memory": {
            "128 ГБ": {
                "price": 17500,
                "colors": ["белый", "черный", "синий", "фиолетовый"],
                "color_indices": {"белый": 0, "черный": 1, "синий": 2, "фиолетовый": 3}
            },
            "256 ГБ": {
                "price": 19000,
                "colors": ["белый", "черный", "синий", "фиолетовый"],
                "color_indices": {"белый": 0, "черный": 1, "синий": 2, "фиолетовый": 3}
            }
        }
    },
    "iPhone 12": {
        "description": "iPhone 12 с дисплеем Super Retina XDR и поддержкой 5G.",
        "memory": {
            "128 ГБ": {
                "price": 20000,
                "colors": ["белый", "черный", "синий", "фиолетовый"],
                "color_indices": {"белый": 0, "черный": 1, "синий": 2, "фиолетовый": 3}
            },
            "256 ГБ": {
                "price": 21500,
                "colors": ["белый", "черный", "синий", "фиолетовый"],
                "color_indices": {"белый": 0, "черный": 1, "синий": 2, "фиолетовый": 3}
            }
        }
    },
    "iPhone 13 mini": {
        "description": "Компактный iPhone 13 mini с улучшенной камерой.",
        "memory": {
            "128 ГБ": {
                "price": 23500,
                "colors": ["черный", "голубой", "белый", "розовый"],
                "color_indices": {"черный": 0, "голубой": 2, "белый": 3, "розовый": 4}
            },
            "256 ГБ": {
                "price": 26000,
                "colors": ["черный", "синий", "голубой", "белый", "розовый"],
                "color_indices": {"черный": 0, "синий": 1, "голубой": 2, "белый": 3, "розовый": 4}
            }
        }
    },
    "iPhone 13": {
        "description": "iPhone 13 с улучшенной автономностью и камерой.",
        "memory": {
            "128 ГБ": {
                "price": 26500,
                "colors": ["черный", "синий", "голубой", "белый", "розовый"],
                "color_indices": {"черный": 0, "синий": 1, "голубой": 2, "белый": 3, "розовый": 4}
            },
            "256 ГБ": {
                "price": 28500,
                "colors": ["черный", "синий", "голубой", "белый", "розовый"],
                "color_indices": {"черный": 0, "синий": 1, "голубой": 2, "белый": 3, "розовый": 4}
            }
        }
    },
    "iPhone 13 Pro": {
        "description": "iPhone 13 Pro с дисплеем ProMotion и тройной камерой.",
        "memory": {
            "128 ГБ": {
                "price": 34500,
                "colors": ["черный", "белый", "голубой", "зеленый"],
                "color_indices": {"черный": 0, "белый": 1, "голубой": 2, "зеленый": 3}
            },
            "256 ГБ": {
                "price": 38000,
                "colors": ["черный", "белый", "голубой", "зеленый"],
                "color_indices": {"черный": 0, "белый": 1, "голубой": 2, "зеленый": 3}
            },
            "512 ГБ": {
                "price": 39500,
                "colors": ["черный", "белый", "голубой", "зеленый"],
                "color_indices": {"черный": 0, "белый": 1, "голубой": 2, "зеленый": 3}
            }
        }
    },
    "iPhone 13 Pro Max": {
        "description": "iPhone 13 Pro Max с самым большим дисплеем в линейке.",
        "memory": {
            "128 ГБ": {
                "price": 40000,
                "colors": ["черный", "белый", "голубой", "зеленый"],
                "color_indices": {"черный": 0, "белый": 1, "голубой": 2, "зеленый": 3}
            },
            "256 ГБ": {
                "price": 43500,
                "colors": ["черный", "белый", "голубой", "зеленый"],
                "color_indices": {"черный": 0, "белый": 1, "голубой": 2, "зеленый": 3}
            },
            "512 ГБ": {
                "price": 44500,
                "colors": ["черный", "белый", "голубой", "зеленый"],
                "color_indices": {"черный": 0, "белый": 1, "голубой": 2, "зеленый": 3}
            }
        }
    },
    "iPhone 14 Pro": {
        "description": "iPhone 14 Pro с динамическим островом и камерой 48 Мп.",
        "memory": {
            "128 ГБ": {
                "price": 42000,
                "colors": ["белый", "золотой", "серебряный", "черный"],
                "color_indices": {"белый": 0, "золотой": 1, "серебряный": 2, "черный": 3}
            },
            "256 ГБ": {
                "price": 44000,
                "colors": ["белый", "золотой", "серебряный", "черный"],
                "color_indices": {"белый": 0, "золотой": 1, "серебряный": 2, "черный": 3}
            },
            "512 ГБ": {
                "price": 45500,
                "colors": ["белый", "золотой", "серебряный", "черный"],
                "color_indices": {"белый": 0, "золотой": 1, "серебряный": 2, "черный": 3}
            }
        }
    },
    "iPhone 14 Pro Max": {
        "description": "iPhone 14 Pro Max с самым большим дисплеем и лучшей камерой.",
        "memory": {
            "256 ГБ": {
                "price": 52000,
                "colors": ["белый", "золотой", "серебряный", "черный"],
                "color_indices": {"белый": 0, "золотой": 1, "серебряный": 2, "черный": 3}
            },
            "512 ГБ": {
                "price": 53000,
                "colors": ["белый", "золотой", "серебряный", "черный"],
                "color_indices": {"белый": 0, "золотой": 1, "серебряный": 2, "черный": 3}
            }
        }
    },
    "iPhone XR в корпусе 17": {
        "description": "iPhone XR в корпусе 17 - доступный вариант с хорошими характеристиками.",
        "memory": {
            "128 ГБ": {
                "price": 17000,
                "colors": ["оранжевый", "белый", "черный"],
                "color_indices": {"оранжевый": 0, "белый": 1, "черный": 2}
            },
            "256 ГБ": {
                "price": 18000,
                "colors": ["оранжевый", "белый", "черный"],
                "color_indices": {"оранжевый": 0, "белый": 1, "черный": 2}
            }
        }
    }
}

# Маппинг названий моделей на имена папок
FOLDER_NAMES = {
    "iPhone 12 mini": "Айфон 12 мини",
    "iPhone 12": "Айфон 12",
    "iPhone 13 mini": "Айфон 13 мини",
    "iPhone 13": "Айфон 13",
    "iPhone 13 Pro": "Айфон 13 про",
    "iPhone 13 Pro Max": "Айфон 13 про макс",
    "iPhone 14 Pro": "Айфон 14 про",
    "iPhone 14 Pro Max": "Айфон 14 про макс",
    "iPhone XR в корпусе 17": "Айфон XR в корпусе 17"
}

# Эмодзи для цветов
COLOR_EMOJIS = {
    "белый": "⚪",
    "черный": "⚫",
    "синий": "🔵",
    "фиолетовый": "🟣",
    "голубой": "🔷",
    "розовый": "🎀",
    "зеленый": "🟢",
    "золотой": "🌟",
    "серебряный": "✨",
    "оранжевый": "🟠"
}

# Хранилище для последнего сообщения каждого пользователя
user_last_messages = {}

def find_image_file(model_name: str, memory: str, color_index: int) -> str:
    """Ищет файл изображения по модели, памяти и индексу цвета"""
    try:
        folder_name = FOLDER_NAMES.get(model_name)
        if not folder_name:
            return None
        
        model_path = os.path.join(IMAGES_BASE_PATH, folder_name)
        if not os.path.exists(model_path):
            return None
        
        # Ищем папку с памятью
        memory_folder = None
        for item in os.listdir(model_path):
            item_path = os.path.join(model_path, item)
            if os.path.isdir(item_path) and memory.lower() in item.lower():
                memory_folder = item_path
                break
        
        if not memory_folder:
            return None
        
        # Ищем файл с нужным индексом
        for file in os.listdir(memory_folder):
            file_lower = file.lower()
            # Проверяем разные варианты
            if (f"{color_index}.png" in file_lower or 
                f"{color_index}.jpg" in file_lower or 
                f"{color_index}.jpeg" in file_lower or
                f" {color_index}." in file_lower):
                return os.path.join(memory_folder, file)
        
        # Если не нашли по индексу, берем первый файл
        image_files = [f for f in os.listdir(memory_folder) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if image_files and color_index < len(image_files):
            return os.path.join(memory_folder, image_files[color_index])
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска изображения: {e}")
        return None

# ================== ФУНКЦИИ МЕНЮ (без изменений) ==================

def get_main_menu():
    """Главное меню"""
    text = """
    🍏 *WORLD APPLE*
    
    🛒 *Магазин оригинальных iPhone*
    
    🔥 *ПРЕИМУЩЕСТВА:*
    • 100% оригинальная техника Apple
    • Гарантия 1 год
    • Профессиональная консультация
    
    👇 *ВЫБЕРИТЕ РАЗДЕЛ:*
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        types.InlineKeyboardButton(text="📱 КАТАЛОГ", callback_data="catalog")
    )
    keyboard.row(
        types.InlineKeyboardButton(text="📍 АДРЕСА", callback_data="addresses"),
        types.InlineKeyboardButton(text="📞 ПОДДЕРЖКА", url=f"https://t.me/{SUPPORT_USERNAME}")
    )
    keyboard.row(
        types.InlineKeyboardButton(text="ℹ️ О НАС", callback_data="about")
    )
    
    return text, keyboard.as_markup()

def get_catalog_menu():
    """Меню каталога"""
    text = """
    📱 *КАТАЛОГ IPHONE*
    
    🎯 *ВЫБЕРИТЕ МОДЕЛЬ:*
    
    Все модели в наличии! ✅
    """
    
    keyboard = InlineKeyboardBuilder()
    models = list(PRODUCTS.keys())
    
    # Разбиваем на 2 колонки для красоты
    for i in range(0, len(models), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(models):
                model = models[i + j]
                # Находим минимальную цену
                min_price = min(PRODUCTS[model]["memory"][mem]["price"] 
                              for mem in PRODUCTS[model]["memory"])
                row_buttons.append(
                    types.InlineKeyboardButton(
                        text=f"{model} • {min_price:,}₽".replace(",", " "),
                        callback_data=f"model_{model.replace(' ', '_')}"
                    )
                )
        
        if len(row_buttons) == 2:
            keyboard.row(row_buttons[0], row_buttons[1])
        else:
            keyboard.row(row_buttons[0])
    
    keyboard.row(
        types.InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="back_to_main")
    )
    
    return text, keyboard.as_markup()

def get_memory_menu(model_name: str):
    """Меню выбора памяти для модели"""
    product = PRODUCTS[model_name]
    
    text = f"""
    🍎 *{model_name}*
    
    📋 *ОПИСАНИЕ:*
    {product['description']}
    
    💰 *ВЫБЕРИТЕ ОБЪЕМ ПАМЯТИ:*
    """
    
    keyboard = InlineKeyboardBuilder()
    
    for memory, info in product["memory"].items():
        price = info["price"]
        keyboard.row(
            types.InlineKeyboardButton(
                text=f"💾 {memory} • {price:,}₽".replace(",", " "),
                callback_data=f"memory_{model_name.replace(' ', '_')}_{memory}"
            )
        )
    
    keyboard.row(
        types.InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="catalog"),
        types.InlineKeyboardButton(text="🏠 ГЛАВНАЯ", callback_data="back_to_main")
    )
    
    return text, keyboard.as_markup()

def get_colors_menu(model_name: str, memory: str):
    """Меню выбора цвета"""
    product = PRODUCTS[model_name]
    memory_info = product["memory"][memory]
    colors = memory_info["colors"]
    price = memory_info["price"]
    
    text = f"""
    📱 *{model_name} {memory}*
    
    💰 *ЦЕНА:* {price:,}₽
    
    🎨 *ВЫБЕРИТЕ ЦВЕТ:*
    """
    
    keyboard = InlineKeyboardBuilder()
    
    # Разбиваем цвета на 2 колонки
    for i in range(0, len(colors), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(colors):
                color = colors[i + j]
                emoji = COLOR_EMOJIS.get(color, "🎨")
                row_buttons.append(
                    types.InlineKeyboardButton(
                        text=f"{emoji} {color.upper()}",
                        callback_data=f"color_{model_name.replace(' ', '_')}_{memory}_{color}"
                    )
                )
        
        if len(row_buttons) == 2:
            keyboard.row(row_buttons[0], row_buttons[1])
        else:
            keyboard.row(row_buttons[0])
    
    keyboard.row(
        types.InlineKeyboardButton(text="⬅️ НАЗАД", callback_data=f"model_{model_name.replace(' ', '_')}"),
        types.InlineKeyboardButton(text="🏠 ГЛАВНАЯ", callback_data="back_to_main")
    )
    
    return text, keyboard.as_markup()

def get_addresses_menu():
    """Меню адресов"""
    text = """
    📍 *НАШИ МАГАЗИНЫ*
    
    🏪 *МОСКВА*
    Тихарецкий бульвар 1с19
    🕒 10:00 - 21:00
    
    
    📱 *ТЕЛЕФОН:* +7(993)616-08-95
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        types.InlineKeyboardButton(text="📞 ПОЗВОНИТЬ", callback_data="call_store")
    )
    keyboard.row(
        types.InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="back_to_main")
    )
    
    return text, keyboard.as_markup()

def get_about_menu():
    """Меню о нас"""
    text = f"""
    🍏 *О КОМПАНИИ WORLD APPLE*
    
    *РАБОТАЕМ С 2015 ГОДА!*
    
    🏆 *НАШИ ПРЕИМУЩЕСТВА:*
    
    ✅ 100% оригинальная техника Apple
    ✅ Официальная гарантия 1 год
    ✅ Профессиональная консультация
    
    📱 *КОНТАКТЫ:*
    
    📞 Телефон: +7(993)616-08-95
    👨‍💼 Поддержка: @{SUPPORT_USERNAME}
    
    🚀 *МЫ ВСЕГДА НА СВЯЗИ!*
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        types.InlineKeyboardButton(text="📞 СВЯЗАТЬСЯ", url=f"https://t.me/{SUPPORT_USERNAME}")
    )
    keyboard.row(
        types.InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="back_to_main")
    )
    
    return text, keyboard.as_markup()

async def update_menu(message: types.Message, text: str, keyboard: types.InlineKeyboardMarkup):
    """Обновляет меню в одном сообщении"""
    user_id = message.from_user.id
    
    try:
        if user_id in user_last_messages:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=user_last_messages[user_id],
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                return user_last_messages[user_id]
            except Exception as e:
                # Если не удалось отредактировать (старое сообщение), отправляем новое
                pass
        
        # Отправляем новое сообщение
        new_message = await message.answer(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        user_last_messages[user_id] = new_message.message_id
        return new_message.message_id
        
    except Exception as e:
        logger.error(f"Ошибка обновления меню: {e}")
        # Отправляем новое сообщение в случае ошибки
        new_message = await message.answer(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        user_last_messages[user_id] = new_message.message_id
        return new_message.message_id

# ================== ФУНКЦИИ ДЛЯ РАБОТЫ С ФОТО ==================

async def upload_all_photos_to_telegram():
    """Загружает ВСЕ фото в Telegram канал и сохраняет file_id"""
    logger.info("🚀 Начинаю загрузку всех фото в Telegram...")
    
    total_count = 0
    uploaded_count = 0
    skipped_count = 0
    
    # Собираем все изображения для загрузки
    for model_name in PRODUCTS:
        product = PRODUCTS[model_name]
        
        for memory in product["memory"]:
            memory_info = product["memory"][memory]
            colors = memory_info["colors"]
            
            for color_index, color_name in enumerate(colors):
                total_count += 1
                
                # Проверяем, есть ли уже в базе
                existing_file_id = await db.get_file_id(model_name, memory, color_index)
                if existing_file_id:
                    logger.debug(f"⏩ Пропускаем (уже в кэше): {model_name} {memory} {color_name}")
                    skipped_count += 1
                    continue
                
                # Ищем файл
                image_path = find_image_file(model_name, memory, color_index)
                if not image_path or not os.path.exists(image_path):
                    logger.warning(f"❌ Файл не найден: {model_name} {memory} {color_name}")
                    continue
                
                try:
                    # Загружаем фото в канал используя FSInputFile
                    photo = FSInputFile(image_path)
                    message = await bot.send_photo(
                        chat_id=STORAGE_CHANNEL_ID,
                        photo=photo,
                        caption=f"#{model_name.replace(' ', '_')} #{memory.replace(' ', '_')} #{color_name}"
                    )
                    
                    # Получаем file_id самого большого размера
                    photo_obj = message.photo[-1]
                    
                    # Сохраняем в базу
                    await db.save_file_id(
                        model_name, memory, color_index,
                        color_name, photo_obj
                    )
                    
                    uploaded_count += 1
                    logger.info(f"✅ Загружено {uploaded_count}/{total_count}: {model_name} {memory} {color_name}")
                    
                    # Небольшая пауза чтобы не спамить
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки {model_name} {memory} {color_name}: {e}")
    
    logger.info(f"🎉 Загрузка завершена! Всего: {total_count}, Загружено: {uploaded_count}, Пропущено: {skipped_count}")
    return uploaded_count

async def send_cached_photo(
    message: types.Message, 
    model: str, 
    memory: str, 
    color_name: str,
    price: int
) -> bool:
    """Отправляет фото из кэша Telegram"""
    try:
        # Получаем color_index
        product = PRODUCTS.get(model)
        if not product:
            return False
        
        memory_info = product["memory"].get(memory)
        if not memory_info:
            return False
        
        color_index = memory_info["color_indices"].get(color_name)
        if color_index is None:
            return False
        
        # Получаем file_id из кэша
        file_id = await db.get_file_id(model, memory, color_index)
        if not file_id:
            logger.warning(f"Фото не найдено в кэше: {model} {memory} {color_name}")
            return False
        
        # Отправляем мгновенно!
        await message.answer_photo(
            photo=file_id,
            caption=f"📱 *{model} {memory}*\n\n🎨 *ЦВЕТ:* {color_name.upper()}\n💰 *ЦЕНА:* {price:,}₽".replace(",", " "),
            parse_mode="Markdown"
        )
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки кэшированного фото: {e}")
        return False

async def send_fallback_photo(
    message: types.Message,
    model: str,
    memory: str,
    color_name: str,
    price: int
):
    """Запасной вариант: отправляет сжатое фото"""
    try:
        # Получаем color_index
        product = PRODUCTS.get(model)
        if not product:
            return False
        
        memory_info = product["memory"].get(memory)
        if not memory_info:
            return False
        
        color_index = memory_info["color_indices"].get(color_name)
        if color_index is None:
            return False
        
        # Ищем файл
        image_path = find_image_file(model, memory, color_index)
        if not image_path or not os.path.exists(image_path):
            await message.answer("📱 Фото временно недоступно")
            return False
        
        # Отправляем как есть
        photo = FSInputFile(image_path)
        await message.answer_photo(
            photo=photo,
            caption=f"📱 *{model} {memory}*\n\n🎨 *ЦВЕТ:* {color_name.upper()}\n💰 *ЦЕНА:* {price:,}₽".replace(",", " "),
            parse_mode="Markdown"
        )
        return True
            
    except Exception as e:
        logger.error(f"Ошибка запасного варианта: {e}")
        await message.answer("❌ Не удалось загрузить фото")
        return False

# ================= ОСНОВНЫЕ ОБРАБОТЧИКИ =================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    text, keyboard = get_main_menu()
    await update_menu(message, text, keyboard)

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    """Команда меню"""
    await cmd_start(message, state)

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback_query: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    text, keyboard = get_main_menu()
    await update_menu(callback_query.message, text, keyboard)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "catalog")
async def show_catalog(callback_query: CallbackQuery, state: FSMContext):
    """Показать каталог"""
    await state.set_state(UserState.viewing_product)
    text, keyboard = get_catalog_menu()
    await update_menu(callback_query.message, text, keyboard)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("model_"))
async def show_model_memory(callback_query: CallbackQuery, state: FSMContext):
    """Показать варианты памяти для модели"""
    try:
        model_key = callback_query.data.replace("model_", "").replace("_", " ")
        
        if model_key not in PRODUCTS:
            await callback_query.answer("❌ Модель не найдена!")
            return
        
        await state.set_state(UserState.viewing_product)
        text, keyboard = get_memory_menu(model_key)
        await update_menu(callback_query.message, text, keyboard)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in show_model_memory: {e}")
        await callback_query.answer("❌ Ошибка!")

@dp.callback_query(lambda c: c.data.startswith("memory_"))
async def show_memory_colors(callback_query: CallbackQuery, state: FSMContext):
    """Показать цвета для выбранной памяти"""
    try:
        data = callback_query.data.replace("memory_", "")
        parts = data.split("_")
        
        # Последняя часть - память
        memory = parts[-1]
        # Остальное - название модели
        model_key = "_".join(parts[:-1]).replace("_", " ")
        
        if model_key not in PRODUCTS:
            await callback_query.answer("❌ Модель не найдена!")
            return
        
        await state.set_state(UserState.viewing_product)
        text, keyboard = get_colors_menu(model_key, memory)
        await update_menu(callback_query.message, text, keyboard)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in show_memory_colors: {e}")
        await callback_query.answer("❌ Ошибка!")

@dp.callback_query(lambda c: c.data.startswith("color_"))
async def show_color_photo_fast(callback_query: CallbackQuery, state: FSMContext):
    """МГНОВЕННАЯ отправка фото через Telegram кэш"""
    try:
        await callback_query.answer("📸 Загружаю фото...")
        
        # Парсим данные
        data = callback_query.data.replace("color_", "")
        parts = data.split("_")
        
        color_name = parts[-1]
        memory = parts[-2]
        model_key = "_".join(parts[:-2]).replace("_", " ")
        
        if model_key not in PRODUCTS:
            await callback_query.answer("❌ Модель не найдена!")
            return
        
        product = PRODUCTS[model_key]
        
        if memory not in product["memory"]:
            await callback_query.answer("❌ Память не найдена!")
            return
        
        memory_info = product["memory"][memory]
        price = memory_info["price"]
        
        # Пробуем отправить из кэша (мгновенно!)
        success = await send_cached_photo(
            callback_query.message,
            model_key,
            memory,
            color_name,
            price
        )
        
        # Если не получилось, используем запасной вариант
        if not success:
            logger.info(f"Использую запасной вариант для {model_key}")
            await send_fallback_photo(
                callback_query.message,
                model_key,
                memory,
                color_name,
                price
            )
        
        # Добавляем кнопки для навигации
        back_keyboard = InlineKeyboardBuilder()
        back_keyboard.row(
            types.InlineKeyboardButton(
                text="⬅️ ВЫБРАТЬ ДРУГОЙ ЦВЕТ",
                callback_data=f"memory_{model_key.replace(' ', '_')}_{memory}"
            )
        )
        back_keyboard.row(
            types.InlineKeyboardButton(
                text="📞 ЗАКАЗАТЬ",
                url=f"https://t.me/{SUPPORT_USERNAME}"
            ),
            types.InlineKeyboardButton(
                text="🏠 ГЛАВНАЯ",
                callback_data="back_to_main"
            )
        )
        
        info_text = f"""
        ✅ *{model_key} {memory} - {color_name.upper()}*
        
        📞 *ДЛЯ ЗАКАЗА:* @{SUPPORT_USERNAME}
        ⚡ *Гарантия 1 год*
        💰 *Цена: {price:,}₽*
        """
        
        await callback_query.message.answer(
            text=info_text.replace(",", " "),
            parse_mode="Markdown",
            reply_markup=back_keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_color_photo_fast: {e}")
        await callback_query.message.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data == "addresses")
async def show_addresses(callback_query: CallbackQuery):
    """Показать адреса магазинов"""
    text, keyboard = get_addresses_menu()
    await update_menu(callback_query.message, text, keyboard)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "call_store")
async def call_store(callback_query: CallbackQuery):
    """Позвонить в магазин"""
    await callback_query.answer("📱 Телефон магазина: +7(993)616-08-95", show_alert=True)

@dp.callback_query(lambda c: c.data == "about")
async def show_about(callback_query: CallbackQuery):
    """Показать информацию о магазине"""
    text, keyboard = get_about_menu()
    await update_menu(callback_query.message, text, keyboard)
    await callback_query.answer()

# ================= АДМИН КОМАНДЫ =================

@dp.message(Command("reload_cache"))
async def cmd_reload_cache(message: Message):
    """Перезагружает кэш фото (только для админа)"""
    # Проверяем админа
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Эта команда только для администратора")
        return
    
    await message.answer("🔄 Начинаю перезагрузку кэша фото... Это может занять несколько минут.")
    
    try:
        count = await upload_all_photos_to_telegram()
        await message.answer(f"✅ Кэш перезагружен! Загружено {count} фото")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("cache_status"))
async def cmd_cache_status(message: Message):
    """Показывает статус кэша"""
    try:
        cached_count = await db.get_cached_count()
        
        # Считаем общее количество фото
        total_count = 0
        for model_name in PRODUCTS:
            product = PRODUCTS[model_name]
            for memory in product["memory"]:
                memory_info = product["memory"][memory]
                total_count += len(memory_info["colors"])
        
        if total_count > 0:
            percentage = (cached_count / total_count) * 100
        else:
            percentage = 0
        
        status_text = f"""
        📊 *СТАТУС КЭША ФОТО*
        
        📁 Всего фото в каталоге: {total_count}
        ✅ Загружено в кэш: {cached_count}
        📈 Заполнение: {percentage:.1f}%
        
        ⚡ *Фото отправляются мгновенно!*
        
        🔄 Обновить кэш: /reload_cache (только админ)
        """
        
        await message.answer(status_text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("clear_cache"))
async def cmd_clear_cache(message: Message):
    """Очищает кэш фото"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Эта команда только для администратора")
        return
    
    try:
        async with aiosqlite.connect("photos.db") as db_conn:
            await db_conn.execute("DELETE FROM photos")
            await db_conn.commit()
        
        await message.answer("✅ Кэш очищен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message()
async def handle_other_messages(message: Message, state: FSMContext):
    """Обработчик других сообщений"""
    await cmd_start(message, state)

async def on_startup():
    """Выполняется при запуске бота"""
    print("=" * 60)
    print("🚀 ЗАПУСК БОТА WORLD APPLE")
    print("=" * 60)
    
    # Проверяем сколько фото уже в кэше
    cached = await db.get_cached_count()
    
    # Считаем сколько должно быть всего
    total_needed = 0
    for model in PRODUCTS:
        for memory in PRODUCTS[model]["memory"]:
            total_needed += len(PRODUCTS[model]["memory"][memory]["colors"])
    
    print(f"📸 Фото в кэше: {cached}/{total_needed}")
    
    if cached < total_needed:
        print(f"⚠️  Кэш неполный! Запустите команду /reload_cache")
        print(f"   чтобы загрузить {total_needed - cached} фото")
    else:
        print("✅ Кэш полный! Фото будут отправляться мгновенно!")
    
    # Информация о боте
    bot_info = await bot.get_me()
    print(f"\n✅ Бот запущен!")
    print(f"🤖 Имя: {bot_info.full_name}")
    print(f"🔗 @{bot_info.username}")
    print(f"🔗 Ссылка: https://t.me/{bot_info.username}")
    
    # Проверка канала
    if STORAGE_CHANNEL_ID == -1001234567890:
        print("\n❌ ВНИМАНИЕ: Не забудьте заменить STORAGE_CHANNEL_ID!")
        print("   Создайте приватный канал и добавьте бота как администратора")
    
    if ADMIN_ID == 123456789:
        print("\n❌ ВНИМАНИЕ: Не забудьте заменить ADMIN_ID на ваш Telegram ID!")
    
    print("=" * 60)

async def main():
    """Основная функция запуска бота"""
    # Запускаем предстартовую проверку
    await on_startup()
    
    print("\n⏳ Бот запущен...")
    print("=" * 60)
    print("💡 Подсказки:")
    print("1. Создайте приватный канал и добавьте бота как админа")
    print("2. Получите ID канала через @username_to_id_bot")
    print("3. Замените STORAGE_CHANNEL_ID в коде")
    print("4. Запустите /reload_cache чтобы загрузить все фото")
    print("=" * 60)
    
    try:
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Бот остановлен")


