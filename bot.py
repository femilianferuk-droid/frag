# main.py
import asyncio
import json
import logging
import os
import string
import random
from datetime import datetime
from typing import List, Dict, Optional

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.methods import DeleteWebhook
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Файл для хранения настроек бота
SETTINGS_FILE = "bot_settings.json"

# Настройки бота по умолчанию
DEFAULT_SETTINGS = {
    "bot_name": "UsernameFinder Bot",
    "welcome_message": "Добро пожаловать в бот поиска свободных username!"
}

# Премиум эмодзи ID
EMOJI = {
    "settings": "5870982283724328568",
    "profile": "5870994129244131212",
    "people": "5870772616305839506",
    "check": "5870633910337015697",
    "cross": "5870657884844462243",
    "search": "5870528606328852614",
    "stats": "5870921681735781843",
    "broadcast": "6039422865189638057",
    "media": "6035128606563241721",
    "back": "5893057118545646106",
    "info": "6028435952299413210",
    "bot": "6030400221232501136",
    "eye": "6037397706505195857",
    "wallet": "5769126056262898415",
    "gift": "6032644646587338669",
    "clock": "5983150113483134607",
    "rocket": "5963103826075456248",
    "pencil": "5870676941614354370",
    "trash": "5870875489362513438",
    "link": "5769289093221454192",
    "notification": "6039486778597970865",
    "key": "6037249452824072506",
    "unlock": "6037496202990194718",
    "house": "5873147866364514353",
    "graph": "5870930636742595124",
    "party": "6041731551845159060",
    "file": "5870528606328852614",
    "smile": "5870764288364252592",
    "download": "6039802767931871481",
    "add_text": "5771851822897566479",
    "code": "5940433880585605708",
    "loading": "5345906554510012647",
    "wallet_send": "5890848474563352982",
    "wallet_accept": "5879814368572478751",
    "user_check": "5891207662678317861",
    "user_cross": "5893192487324880883",
    "hidden": "6037243349675544634",
    "paperclip": "6039451237743595514",
    "font": "5870801517140775623",
    "write": "5870753782874246579",
    "box": "5884479287171485878",
    "calendar": "5890937706803894250",
    "tag": "5886285355279193209",
    "time_past": "5775896410780079073",
    "apps": "5778672437122045013",
    "brush": "6050679691004612757",
    "money": "5904462880941545555",
    "crypto_bot": "5260752406890711732",
    "geo": "6042011682497106307",
    "resolution": "5778479949572738874",
    "telegram": "6030400221232501136"
}


def load_settings() -> dict:
    """Загрузка настроек из файла"""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    """Сохранение настроек в файл"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# Загружаем настройки при старте
bot_settings = load_settings()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище данных
users_db: Dict[int, dict] = {}
search_history: List[dict] = []
media_files: Dict[str, str] = {}
broadcast_messages: List[dict] = []


# ==================== FSM Состояния ====================

class SearchStates(StatesGroup):
    waiting_for_length = State()
    waiting_for_keywords = State()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()


class SettingsStates(StatesGroup):
    waiting_for_bot_name = State()
    waiting_for_welcome_message = State()


class MediaStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_media = State()


# ==================== Вспомогательные функции ====================

def is_admin(user_id: int) -> bool:
    """Проверка на администратора"""
    return user_id in ADMIN_IDS


def get_main_menu_keyboard() -> types.InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Поиск username",
        callback_data="menu_search",
        style="primary",
        icon_custom_emoji_id=EMOJI["search"]
    ))
    builder.row(types.InlineKeyboardButton(
        text="Профиль",
        callback_data="menu_profile",
        style="default",
        icon_custom_emoji_id=EMOJI["profile"]
    ))
    return builder.as_markup()


def get_search_length_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура выбора длины username"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="5 букв",
            callback_data="search_length_5",
            style="primary",
            icon_custom_emoji_id=EMOJI["tag"]
        ),
        types.InlineKeyboardButton(
            text="6 букв",
            callback_data="search_length_6",
            style="primary",
            icon_custom_emoji_id=EMOJI["tag"]
        )
    )
    builder.row(types.InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_main",
        style="default",
        icon_custom_emoji_id=EMOJI["back"]
    ))
    return builder.as_markup()


def get_admin_panel_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Статистика",
        callback_data="admin_stats",
        style="primary",
        icon_custom_emoji_id=EMOJI["stats"]
    ))
    builder.row(types.InlineKeyboardButton(
        text="Рассылка",
        callback_data="admin_broadcast",
        style="success",
        icon_custom_emoji_id=EMOJI["broadcast"]
    ))
    builder.row(types.InlineKeyboardButton(
        text="Добавить медиа",
        callback_data="admin_add_media",
        style="primary",
        icon_custom_emoji_id=EMOJI["media"]
    ))
    builder.row(
        types.InlineKeyboardButton(
            text="Название бота",
            callback_data="admin_change_name",
            style="default",
            icon_custom_emoji_id=EMOJI["font"]
        ),
        types.InlineKeyboardButton(
            text="Приветствие",
            callback_data="admin_change_welcome",
            style="default",
            icon_custom_emoji_id=EMOJI["write"]
        )
    )
    return builder.as_markup()


def get_back_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_admin",
        style="default",
        icon_custom_emoji_id=EMOJI["back"]
    ))
    return builder.as_markup()


def get_broadcast_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура для рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Добавить медиа",
        callback_data="broadcast_add_media",
        style="primary",
        icon_custom_emoji_id=EMOJI["media"]
    ))
    builder.row(
        types.InlineKeyboardButton(
            text="Отправить",
            callback_data="broadcast_send",
            style="success",
            icon_custom_emoji_id=EMOJI["rocket"]
        ),
        types.InlineKeyboardButton(
            text="Отмена",
            callback_data="broadcast_cancel",
            style="danger",
            icon_custom_emoji_id=EMOJI["cross"]
        )
    )
    return builder.as_markup()


def get_broadcast_confirm_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Подтвердить",
            callback_data="broadcast_confirm",
            style="success",
            icon_custom_emoji_id=EMOJI["check"]
        ),
        types.InlineKeyboardButton(
            text="Отмена",
            callback_data="broadcast_cancel",
            style="danger",
            icon_custom_emoji_id=EMOJI["cross"]
        )
    )
    return builder.as_markup()


async def check_username_availability(username: str) -> bool:
    """
    Проверка доступности username через Telegram API.
    Пробуем получить информацию о пользователе через resolveUsername.
    Если пользователь не найден - username свободен.
    """
    try:
        # Используем метод resolveUsername из Telegram Bot API
        # Если username занят, вернется информация о пользователе/канале
        # Если свободен - ошибка 400
        async with aiohttp.ClientSession() as session:
            url = f"https://t.me/{username}"
            async with session.get(url, allow_redirects=False) as response:
                # Если редирект на страницу пользователя - username занят
                if response.status == 302:
                    return False
                # Если страница не найдена - username может быть свободен
                elif response.status == 404:
                    return True
                # Если успешный ответ - проверяем контент
                elif response.status == 200:
                    text = await response.text()
                    # Проверяем наличие признаков занятого username
                    if 'tgme_page_title' in text or 'tgme_page_photo' in text:
                        return False
                    return True
                return False
    except Exception as e:
        logger.error(f"Ошибка при проверке t.me/{username}: {e}")
        # Альтернативный метод через Bot API
        return await check_username_via_bot_api(username)


async def check_username_via_bot_api(username: str) -> bool:
    """
    Проверка через getChat метод Bot API.
    Если можем получить чат - username занят.
    """
    try:
        chat = await bot.get_chat(f"@{username}")
        # Если получили чат - username занят
        return False
    except Exception as e:
        error_message = str(e)
        # Если ошибка "chat not found" или "user not found" - username свободен
        if "chat not found" in error_message.lower() or "not found" in error_message.lower():
            return True
        # Другие ошибки
        logger.error(f"Ошибка Bot API при проверке @{username}: {e}")
        return False


def generate_usernames(length: int, keywords: List[str] = None, count: int = 200) -> List[str]:
    """Генерация username заданной длины с ключевыми словами"""
    letters = string.ascii_lowercase + string.digits
    # Не используем цифры в начале
    first_letters = string.ascii_lowercase
    generated = set()
    result = []
    
    if keywords:
        # Сначала генерируем username с ключевыми словами
        for keyword in keywords:
            keyword = keyword.lower().strip()
            # Убираем небуквенные символы из ключевого слова
            keyword = ''.join(c for c in keyword if c.isalnum())
            if not keyword:
                continue
                
            remaining_length = length - len(keyword)
            if remaining_length < 0:
                continue
            
            attempts = 0
            while len(result) < count and attempts < count * 2:
                attempts += 1
                
                if remaining_length > 0:
                    prefix_len = random.randint(0, remaining_length)
                    suffix_len = remaining_length - prefix_len
                    
                    prefix = ''.join(random.choices(letters, k=prefix_len))
                    suffix = ''.join(random.choices(letters, k=suffix_len))
                    
                    username = prefix + keyword + suffix
                else:
                    username = keyword
                
                # Проверяем что username начинается с буквы
                if username and username[0].isdigit():
                    username = random.choice(first_letters) + username[1:]
                
                if username not in generated:
                    generated.add(username)
                    result.append(username)
    else:
        # Генерируем случайные username
        while len(result) < count:
            username = random.choice(first_letters) + ''.join(random.choices(letters, k=length-1))
            if username not in generated:
                generated.add(username)
                result.append(username)
    
    return result


async def search_free_usernames(length: int, keywords: List[str] = None, max_results: int = 15) -> List[str]:
    """Поиск свободных username с параллельной проверкой"""
    free_usernames = []
    
    # Генерируем больше username для проверки
    usernames_to_check = generate_usernames(length, keywords, count=300)
    
    # Проверяем username батчами по 10 штук параллельно
    batch_size = 10
    
    for i in range(0, len(usernames_to_check), batch_size):
        batch = usernames_to_check[i:i+batch_size]
        
        # Параллельная проверка батча
        tasks = [check_username_via_bot_api(username) for username in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собираем свободные username
        for username, is_free in zip(batch, results):
            if isinstance(is_free, bool) and is_free:
                free_usernames.append(username)
                if len(free_usernames) >= max_results:
                    return free_usernames
        
        # Небольшая задержка между батчами
        await asyncio.sleep(0.1)
    
    return free_usernames


# ==================== Обработчики команд ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    # Сохраняем пользователя в БД
    if user_id not in users_db:
        users_db[user_id] = {
            "id": user_id,
            "username": message.from_user.username,
            "full_name": full_name,
            "joined_date": datetime.now().isoformat(),
            "searches": 0
        }
    
    welcome_text = f'<b>{bot_settings["bot_name"]}</b>\n\n{bot_settings["welcome_message"]}'
    
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer(
            f'<b><tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Нет доступа</b>',
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["settings"]}">⚙</tg-emoji> Админ-панель</b>',
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )


# ==================== Главное меню ====================

@dp.callback_query(F.data == "menu_search")
async def menu_search_callback(callback: types.CallbackQuery, state: FSMContext):
    """Поиск username"""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["search"]}">📁</tg-emoji> Выберите длину username для поиска:</b>',
        parse_mode="HTML",
        reply_markup=get_search_length_keyboard()
    )
    await state.set_state(SearchStates.waiting_for_length)
    await callback.answer()


@dp.callback_query(F.data == "menu_profile")
async def menu_profile_callback(callback: types.CallbackQuery):
    """Профиль пользователя"""
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    
    profile_text = f'''
<b><tg-emoji emoji-id="{EMOJI["profile"]}">👤</tg-emoji> Ваш профиль</b>

<b>ID:</b> <code>{user_id}</code>
<b>Поисков выполнено:</b> {user_data.get("searches", 0)}
<b>Дата регистрации:</b> {user_data.get("joined_date", "Неизвестно")}
'''
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_main",
        style="default",
        icon_custom_emoji_id=EMOJI["back"]
    ))
    
    await callback.message.edit_text(
        profile_text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    welcome_text = f'<b>{bot_settings["bot_name"]}</b>\n\n{bot_settings["welcome_message"]}'
    await callback.message.edit_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


# ==================== Поиск username ====================

@dp.callback_query(F.data.startswith("search_length_"))
async def process_length_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора длины username"""
    length = int(callback.data.split("_")[2])
    await state.update_data(length=length)
    
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["write"]}">✍</tg-emoji> Введите ключевые слова через пробел\n(или отправьте "0" для случайного поиска):</b>',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SearchStates.waiting_for_keywords)
    await callback.answer()


@dp.callback_query(F.data == "new_search")
async def new_search_callback(callback: types.CallbackQuery, state: FSMContext):
    """Новый поиск"""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["search"]}">📁</tg-emoji> Выберите длину username для поиска:</b>',
        parse_mode="HTML",
        reply_markup=get_search_length_keyboard()
    )
    await state.set_state(SearchStates.waiting_for_length)
    await callback.answer()


@dp.message(StateFilter(SearchStates.waiting_for_keywords))
async def process_keywords(message: types.Message, state: FSMContext):
    """Обработка ключевых слов и запуск поиска"""
    try:
        await message.delete()
    except:
        pass
    
    keywords = None
    if message.text and message.text.strip() != "0":
        keywords = message.text.lower().split()
    
    data = await state.get_data()
    length = data.get("length", 5)
    
    # Сообщение о начале поиска
    loading_text = f'<b><tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> Ищем свободные username длиной {length} символов...</b>'
    if keywords:
        loading_text += f'\n<b>Ключевые слова: {", ".join(keywords)}</b>'
    
    status_msg = await message.answer(loading_text, parse_mode="HTML")
    
    # Запускаем поиск
    free_usernames = await search_free_usernames(
        length=length,
        keywords=keywords,
        max_results=15
    )
    
    # Обновляем статистику
    user_id = message.from_user.id
    if user_id in users_db:
        users_db[user_id]["searches"] = users_db[user_id].get("searches", 0) + 1
    
    # Удаляем статусное сообщение
    try:
        await status_msg.delete()
    except:
        pass
    
    # Формируем результат
    if free_usernames:
        result_text = f'<b><tg-emoji emoji-id="{EMOJI["party"]}">🎉</tg-emoji> Найдены свободные username ({len(free_usernames)}):</b>\n\n'
        
        for i, username in enumerate(free_usernames, 1):
            result_text += f'<b>{i}.</b> @{username}\n'
        
        result_text += f'\n<b><tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Нажмите на кнопку чтобы открыть username в Telegram</b>'
        
        # Создаем кнопки со ссылками на Telegram
        builder = InlineKeyboardBuilder()
        
        # Добавляем кнопки для первых 10 username
        for i, username in enumerate(free_usernames[:10], 1):
            telegram_link = f"https://t.me/{username}"
            style = "primary" if i <= 5 else "success"
            builder.row(types.InlineKeyboardButton(
                text=f"@{username}",
                url=telegram_link,
                style=style,
                icon_custom_emoji_id=EMOJI["telegram"]
            ))
        
        # Кнопки навигации
        builder.row(types.InlineKeyboardButton(
            text="Новый поиск",
            callback_data="new_search",
            style="primary",
            icon_custom_emoji_id=EMOJI["search"]
        ))
        builder.row(types.InlineKeyboardButton(
            text="Главное меню",
            callback_data="back_to_main",
            style="default",
            icon_custom_emoji_id=EMOJI["back"]
        ))
        
        await message.answer(
            result_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
            disable_web_page_preview=True
        )
    else:
        result_text = f'<b><tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Свободные username не найдены</b>\n\nПопробуйте другие параметры поиска.'
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="Новый поиск",
            callback_data="new_search",
            style="primary",
            icon_custom_emoji_id=EMOJI["search"]
        ))
        builder.row(types.InlineKeyboardButton(
            text="Главное меню",
            callback_data="back_to_main",
            style="default",
            icon_custom_emoji_id=EMOJI["back"]
        ))
        
        await message.answer(
            result_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    
    await state.clear()


# ==================== Админ-панель ====================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    """Статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    total_users = len(users_db)
    total_searches = sum(user.get("searches", 0) for user in users_db.values())
    
    stats_text = f'''
<b><tg-emoji emoji-id="{EMOJI["stats"]}">📊</tg-emoji> Статистика бота</b>

<b><tg-emoji emoji-id="{EMOJI["people"]}">👥</tg-emoji> Всего пользователей:</b> {total_users}
<b><tg-emoji emoji-id="{EMOJI["search"]}">📁</tg-emoji> Всего поисков:</b> {total_searches}
<b><tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> Сегодня:</b> {datetime.now().strftime("%d.%m.%Y")}
'''
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Обновить",
        callback_data="admin_stats",
        style="primary",
        icon_custom_emoji_id=EMOJI["loading"]
    ))
    builder.row(types.InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_admin",
        style="default",
        icon_custom_emoji_id=EMOJI["back"]
    ))
    
    await callback.message.edit_text(stats_text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await state.clear()
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["settings"]}">⚙</tg-emoji> Админ-панель</b>',
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_callback(callback: types.CallbackQuery, state: FSMContext):
    """Начало рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["broadcast"]}">📣</tg-emoji> Отправьте сообщение для рассылки:</b>',
        parse_mode="HTML",
        reply_markup=get_broadcast_keyboard()
    )
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.answer()


@dp.message(StateFilter(BroadcastStates.waiting_for_message))
async def broadcast_message_handler(message: types.Message, state: FSMContext):
    """Получение сообщения для рассылки"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_data = {
        "text": message.html_text if message.text else message.caption,
        "media_type": None,
        "media_id": None
    }
    
    if message.photo:
        broadcast_data["media_type"] = "photo"
        broadcast_data["media_id"] = message.photo[-1].file_id
    elif message.video:
        broadcast_data["media_type"] = "video"
        broadcast_data["media_id"] = message.video.file_id
    
    await state.update_data(broadcast_data=broadcast_data)
    
    preview_text = f'''
<b><tg-emoji emoji-id="{EMOJI["eye"]}">👁</tg-emoji> Предпросмотр рассылки:</b>

{broadcast_data["text"]}

<b>Получатели:</b> {len(users_db)} пользователей
'''
    
    await message.answer(preview_text, parse_mode="HTML", reply_markup=get_broadcast_confirm_keyboard())
    await state.set_state(BroadcastStates.waiting_for_confirmation)


@dp.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm_callback(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение и отправка рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    broadcast_data = data.get("broadcast_data", {})
    
    success_count = 0
    fail_count = 0
    
    for user_id in users_db:
        try:
            await bot.send_message(chat_id=user_id, text=broadcast_data["text"], parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            fail_count += 1
    
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Рассылка завершена</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["user_check"]}">👤✅</tg-emoji> Успешно: {success_count}\n'
        f'<tg-emoji emoji-id="{EMOJI["user_cross"]}">👤❌</tg-emoji> Ошибок: {fail_count}',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await state.clear()
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Рассылка отменена</b>',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_change_name")
async def change_name_callback(callback: types.CallbackQuery, state: FSMContext):
    """Изменение названия бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["font"]}">🔗</tg-emoji> Текущее название:</b> {bot_settings["bot_name"]}\n\n'
        '<b>Отправьте новое название:</b>',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SettingsStates.waiting_for_bot_name)
    await callback.answer()


@dp.message(StateFilter(SettingsStates.waiting_for_bot_name))
async def process_bot_name(message: types.Message, state: FSMContext):
    """Обработка нового названия"""
    if not is_admin(message.from_user.id):
        return
    
    new_name = message.text
    bot_settings["bot_name"] = new_name
    save_settings(bot_settings)
    
    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Название изменено:</b> {new_name}',
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "admin_change_welcome")
async def change_welcome_callback(callback: types.CallbackQuery, state: FSMContext):
    """Изменение приветствия"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["write"]}">✍</tg-emoji> Текущее приветствие:</b>\n\n{bot_settings["welcome_message"]}\n\n'
        '<b>Отправьте новое приветствие:</b>',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SettingsStates.waiting_for_welcome_message)
    await callback.answer()


@dp.message(StateFilter(SettingsStates.waiting_for_welcome_message))
async def process_welcome_message(message: types.Message, state: FSMContext):
    """Обработка нового приветствия"""
    if not is_admin(message.from_user.id):
        return
    
    new_welcome = message.text
    bot_settings["welcome_message"] = new_welcome
    save_settings(bot_settings)
    
    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Приветствие изменено:</b>\n\n{new_welcome}',
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "admin_add_media")
async def add_media_callback(callback: types.CallbackQuery, state: FSMContext):
    """Добавление медиа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["media"]}">🖼</tg-emoji> Отправьте категорию для медиа:</b>',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(MediaStates.waiting_for_category)
    await callback.answer()


@dp.message(StateFilter(MediaStates.waiting_for_category))
async def process_media_category(message: types.Message, state: FSMContext):
    """Обработка категории"""
    if not is_admin(message.from_user.id):
        return
    
    category = message.text.lower()
    await state.update_data(media_category=category)
    
    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["media"]}">🖼</tg-emoji> Отправьте фото для "{category}":</b>',
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(MediaStates.waiting_for_media)


@dp.message(StateFilter(MediaStates.waiting_for_media))
async def process_media_file(message: types.Message, state: FSMContext):
    """Обработка медиа"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    category = data.get("media_category", "default")
    
    if message.photo:
        media_files[category] = message.photo[-1].file_id
        await message.answer(
            f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Медиа добавлено в "{category}"</b>',
            parse_mode="HTML",
            reply_markup=get_admin_panel_keyboard()
        )
    else:
        await message.answer(
            f'<b><tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Отправьте фото</b>',
            parse_mode="HTML"
        )
        return
    
    await state.clear()


# ==================== Запуск ====================

async def main():
    logger.info("Бот запускается...")
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
