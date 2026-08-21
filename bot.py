import asyncio
import logging
import os
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ecomlena")
PRIVACY_URL = os.getenv("PRIVACY_URL", "https://your-domain.ru/privacy")

# ЛЕНДИНГИ ПРАКТИКУМОВ И БАНДЛА
URL_BUNDLE = "https://ecomlena.ru/bundle"
URL_NISHA = "https://ecomlena.ru/zolotayanisha"
URL_CHINA = "https://ecomlena.ru/china"
URL_PACKING = "https://ecomlena.ru/packing"

# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DB_NAME = "bot_users.db"


# --- ИНИЦИАЛИЗА БАЗЫ ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                segment TEXT DEFAULT 'general',
                created_at TEXT
            )
        """
        )
        await db.commit()


async def register_user(user: types.User, segment: str = "general"):
    async with aiosqlite.connect(DB_NAME) as db:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id, username, full_name, segment, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user.id, user.username, user.full_name, segment, created_at),
        )
        await db.execute(
            "UPDATE users SET segment = ? WHERE user_id = ?", (segment, user.id)
        )
        await db.commit()


# --- FSM ДЛЯ АДМИН-РАССЫЛКИ ---
class BroadcastState(StatesGroup):
    waiting_for_message = State()


# --- КНОПКИ ДЛЯ КАЖДОГО НАПРАВЛЕНИЯ ---
def get_bundle_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Забронировать Бандл 3-в-1 со скидкой",
                    url=URL_BUNDLE,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Авторский Telegram-канал",
                    url=f"https://t.me/{CHANNEL_ID.replace('@', '')}",
                )
            ],
        ]
    )


def get_nisha_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Посмотреть практикум «Маржинальные ниши»",
                    url=URL_NISHA,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔥 Заберите Полный Бандл 3-в-1", url=URL_BUNDLE
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Авторский Telegram-канал",
                    url=f"https://t.me/{CHANNEL_ID.replace('@', '')}",
                )
            ],
        ]
    )


def get_china_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Посмотреть практикум «Импорт из Китая & 1688»",
                    url=URL_CHINA,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔥 Заберите Полный Бандл 3-в-1", url=URL_BUNDLE
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Авторский Telegram-канал",
                    url=f"https://t.me/{CHANNEL_ID.replace('@', '')}",
                )
            ],
        ]
    )


def get_smysly_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Посмотреть практикум «Продающие Смыслы»",
                    url=URL_PACKING,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔥 Заберите Полный Бандл 3-в-1", url=URL_BUNDLE
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Авторский Telegram-канал",
                    url=f"https://t.me/{CHANNEL_ID.replace('@', '')}",
                )
            ],
        ]
    )


# --- ПРОВЕРКА ПОДПИСКИ НА ТЕЛЕГРАМ-КАНАЛ ---
async def check_subscription(user_id: int) -> bool:
    if not CHANNEL_ID or CHANNEL_ID == "@your_channel":
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.warning(f"Ошибка проверки подписки: {e}")
        return True


# --- АВТОДОГРЕВ ДО БАНДЛА (ЧЕРЕЗ 24 ЧАСА) ---
async def schedule_bundle_upsell(chat_id: int, lead_magnet_name: str):
    await asyncio.sleep(86400)  # 24 часа
    upsell_text = (
        f"📊 <b>Вчера вы забирали материалы по теме «{lead_magnet_name}».</b>\n\n"
        "Знаете, какая главная ошибка селлеров? Наладить один процесс, но провалиться в других.\n\n"
        "Товарный бизнес — это **Треугольник Успеха**:\n"
        "1️⃣ Маржинальная узкая ниша\n"
        "2️⃣ Прямой белый/карго импорт из Китая\n"
        "3️⃣ Продающие смыслы и упаковка\n\n"
        "Заберите **Полный Бандл из 3-х Практикумов**, чтобы закрыть все 3 направления под ключ со скидкой 30%!"
    )
    try:
        await bot.send_message(
            chat_id,
            upsell_text,
            parse_mode="HTML",
            reply_markup=get_bundle_keyboard(),
        )
    except Exception as e:
        logging.error(f"Ошибка отправки догрева: {e}")


# --- ВЫДАЧА 5 МИНИ-УРОКОВ ---
async def send_lesson(chat_id: int, lesson_num: int):
    lessons_data = {
        1: {
            "title": "🎓 Урок 1/5: «Правда о e-Commerce 2026: почему 90% новичков теряют деньги?»",
            "text": "В этом подкасте разберем, почему демпинг и масс-маркет на WB — путь к банкротству, и в чем секрет системного маркетинга.\n\n👇 Слушайте подкаст и изучайте PDF-гайд:",
            "audio": "files/lesson1_audio.mp3",
            "pdf": "files/lesson1_guide.pdf",
            "next_btn": InlineKeyboardButton(
                text="Смотреть Урок 2 ➡️", callback_data="lesson_2"
            ),
        },
        2: {
            "title": "🎓 Урок 2/5: «3 безопасные модели старта: Дропшиппинг, Байерство и Микро-партии»",
            "text": "Как начать товарный бизнес без огромного капитала. Разбор моделей с вложениями от 0 ₽.\n\n👇 Слушайте подкаст и изучайте PDF-гайд:",
            "audio": "files/lesson2_audio.mp3",
            "pdf": "files/lesson2_guide.pdf",
            "next_btn": InlineKeyboardButton(
                text="Смотреть Урок 3 ➡️", callback_data="lesson_3"
            ),
        },
        3: {
            "title": "🎓 Урок 3/5: «Математика Узких Ниш: Закуп 400 ₽ ➔ Продажа 2 800 ₽»",
            "text": "Почему продавать 50 коробок с чистой маржой 40%+ в 10 раз выгоднее, чем 1000 коробок в минус.\n\n👇 Слушайте подкаст и изучайте PDF-гайд:",
            "audio": "files/lesson3_audio.mp3",
            "pdf": "files/lesson3_guide.pdf",
            "next_btn": InlineKeyboardButton(
                text="Смотреть Урок 4 ➡️", callback_data="lesson_4"
            ),
        },
        4: {
            "title": "🎓 Урок 4/5: «3 Смертельные ошибки закупа на 1688 и логистики в Китае»",
            "text": "Как отличать перекупщиков от настоящих фабрик и 3 безопасных маршрута ввоза 2026 года.\n\n👇 Слушайте подкаст и изучайте PDF-гайд:",
            "audio": "files/lesson4_audio.mp3",
            "pdf": "files/lesson4_guide.pdf",
            "next_btn": InlineKeyboardButton(
                text="Смотреть Урок 5 ➡️", callback_data="lesson_5"
            ),
        },
        5: {
            "title": "🎓 Урок 5/5: «Пошаговая дорожная карта 2026 и Ваш Главный Инструментарий»",
            "text": "Собираем единый системный бизнес: Ниша + Импорт + Смыслы. Пошаговый алгоритм действий.\n\n👇 Слушайте подкаст и изучайте Дорожную карту:",
            "audio": "files/lesson5_audio.mp3",
            "pdf": "files/lesson5_guide.pdf",
            "next_btn": None,
        },
    }

    lesson = lessons_data.get(lesson_num)
    if not lesson:
        return

    await bot.send_message(
        chat_id, f"<b>{lesson['title']}</b>\n\n{lesson['text']}", parse_mode="HTML"
    )

    if os.path.exists(lesson["audio"]):
        await bot.send_audio(chat_id, FSInputFile(lesson["audio"]))

    if os.path.exists(lesson["pdf"]):
        kb = (
            InlineKeyboardMarkup(inline_keyboard=[[lesson["next_btn"]]])
            if lesson["next_btn"]
            else None
        )
        await bot.send_document(
            chat_id,
            FSInputFile(lesson["pdf"]),
            reply_markup=kb or get_bundle_keyboard(),
        )

    if lesson_num == 5:
        await asyncio.sleep(2)
        await bot.send_message(
            chat_id,
            "🔥 <b>Вы прошли весь бесплатный мини-курс!</b>\n\n"
            "Чтобы построить системный бизнес под ключ без ошибок — заберите **Полный Бандл из 3-х Практикумов** со специальной скидкой!",
            parse_mode="HTML",
            reply_markup=get_bundle_keyboard(),
        )


# --- ЕДИНЫЙ ОБРАБОТЧИК ЗАПРОСОВ (ПРОВЕРКА ПОДПИСКИ + ВЫДАЧА) ---
async def process_user_request(message: types.Message, keyword: str):
    user_id = message.from_user.id
    await register_user(message.from_user, segment=f"lead_{keyword}")

    # 1. Проверка подписки на канал
    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 1. Подписаться на канал",
                        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 2. Я подписался, проверить",
                        callback_data=f"check_sub_{keyword}",
                    )
                ],
            ]
        )
        await message.answer(
            "🔒 **Для получения материала подпишитесь на наш авторский Telegram-канал ecomlena:**\n\n"
            "Там выходят ежедневные разборы узких ниш, аналитика импорта из Китая и живые эфиры!",
            parse_mode="Markdown",
            reply_markup=kb,
        )
        return

    # 2. Выдача контента по кодовому слову
    legal_note = f"\n\nℹ️ *Продолжая использовать бота, вы даете согласие на обработку персональных данных (152-ФЗ) и соглашаетесь с [Политикой конфиденциальности]({PRIVACY_URL}).*"

    if keyword in ["старт", "start"]:
        await message.answer(
            "👋 **Приветствую!** Рада видеть вас на бесплатном Тест-Драйве Товарного Бизнеса 2026!"
            + legal_note,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        await send_lesson(message.chat.id, 1)

    elif keyword == "маржа":
        await message.answer(
            "📊 **Выдаю материалы по Юнит-Экономике и Узким Нишам:**"
            + legal_note,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        if os.path.exists("files/calc_unit_economy.xlsx"):
            await message.answer_document(
                FSInputFile("files/calc_unit_economy.xlsx"),
                caption="🧮 Интерактивный Калькулятор 2.0",
            )
        if os.path.exists("files/15_niches_2026.pdf"):
            await message.answer_document(
                FSInputFile("files/15_niches_2026.pdf"),
                caption="📖 Гайд «15 узких ниш 2026 года»",
            )

        # Сообщение-догрев
        await message.answer(
            "💡 **Хотите глубже освоить поиск прибыльных ниш и юнит-экономику?**\n\n"
            "Посмотреть практикум №1 или заберите полный Бандл 3-в-1 со скидкой!",
            parse_mode="Markdown",
            reply_markup=get_nisha_keyboard(),
        )
        asyncio.create_task(
            schedule_bundle_upsell(message.chat.id, "Маржа и Юнит-экономика")
        )

    elif keyword == "китай":
        await message.answer(
            "🇨🇳 **Выдаю материалы по Закупкам и Логистике в Китае:**"
            + legal_note,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        if os.path.exists("files/import_routes_2026.pdf"):
            await message.answer_document(
                FSInputFile("files/import_routes_2026.pdf"),
                caption="🗺️ Гайд «Безопасный импорт 2026»",
            )
        if os.path.exists("files/1688_traps.pdf"):
            await message.answer_document(
                FSInputFile("files/1688_traps.pdf"),
                caption="🎯 Чек-лист «7 ловушек на 1688»",
            )

        # Сообщение-догрев
        await message.answer(
            "💡 **Хотите закупать товары напрямую на фабриках Китая без посредников?**\n\n"
            "Посмотреть практикум №2 по закупкам на 1688 и карго/белой логистике!",
            parse_mode="Markdown",
            reply_markup=get_china_keyboard(),
        )
        asyncio.create_task(
            schedule_bundle_upsell(
                message.chat.id, "Закупки в Китае и Логистика"
            )
        )

    elif keyword == "смыслы":
        await message.answer(
            "🧠 **Выдаю материалы по Продающим Смыслам и Упаковке:**"
            + legal_note,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        if os.path.exists("files/offer_constructor.pdf"):
            await message.answer_document(
                FSInputFile("files/offer_constructor.pdf"),
                caption="🛠️ Гайд «Конструктор продающих смыслов»",
            )
        if os.path.exists("files/5_packaging_errors.pdf"):
            await message.answer_document(
                FSInputFile("files/5_packaging_errors.pdf"),
                caption="⚠️ Гайд «5 ошибок упаковки карточек»",
            )

        # Сообщение-догрев
        await message.answer(
            "💡 **Хотите создавать офферы, которые продают дорого без демпинга?**\n\n"
            "Посмотреть практикум №3 по продающим смысловым упаковкам!",
            parse_mode="Markdown",
            reply_markup=get_smysly_keyboard(),
        )
        asyncio.create_task(
            schedule_bundle_upsell(
                message.chat.id, "Продающие Смыслы и Офферы"
            )
        )

    elif keyword == "практикум":
        text = (
            "🏗️ **Линейка Практикумов от Дипломированного Маркетолога:**\n\n"
            "1️⃣ **Практикум №1:** Поиск Маржинальных Ниш & Юнит-экономика\n"
            "2️⃣ **Практикум №2:** Безопасные закупки в Китае на 1688 & Логистика\n"
            "3️⃣ **Практикум №3:** Продающие Смыслы & Авито/МП/Соцсети\n\n"
            "🔥 **ПОЛНЫЙ БАНДЛ 3-в-1:** Заберите все 3 Практикума со скидкой 30%!"
            + legal_note
        )
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_bundle_keyboard(),
            disable_web_page_preview=True,
        )


# --- ОБРАБОТЧИК КНОПКИ «СТАРТ» С ДИПЛИНКАМИ И МЕНЮ ---
@dp.message(CommandStart())
async def handle_start_with_menu(
    message: types.Message, command: CommandObject
):
    args = command.args

    if args == "marzha":
        await process_user_request(message, "маржа")
        return
    elif args == "china":
        await process_user_request(message, "китай")
        return
    elif args == "smysly":
        await process_user_request(message, "смыслы")
        return
    elif args == "praktikum":
        await process_user_request(message, "практикум")
        return
    elif args in ["start_course", "start"]:
        await process_user_request(message, "старт")
        return

    welcome_menu_text = (
        "👋 **Добро пожаловать в бот экспертного маркетинга в e-Commerce!**\n\n"
        "Выберите направление, которое вас интересует, нажав на кнопку ниже:"
    )

    menu_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎓 Я Новичок: Пройти 5 уроков",
                    callback_data="menu_start",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 МАРЖА: Калькулятор & Маржинальные ниши",
                    callback_data="menu_marzha",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇨🇳 КИТАЙ: Импорт & Закупки на 1688",
                    callback_data="menu_china",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧠 СМЫСЛЫ: Продающие смыслы & Упаковка",
                    callback_data="menu_smysly",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔥 Полный Бандл 3-в-1", callback_data="menu_praktikum"
                )
            ],
        ]
    )

    await message.answer(
        welcome_menu_text, parse_mode="Markdown", reply_markup=menu_keyboard
    )


# --- ОБРАБОТКА НАЖАТИЙ НА КНОПКИ МЕНЮ И CALLBACKS ---
@dp.callback_query(F.data.startswith("menu_"))
async def process_menu_click(callback: types.CallbackQuery):
    action = callback.data.replace("menu_", "")
    await callback.answer()

    if action == "start":
        await process_user_request(callback.message, "старт")
    elif action == "marzha":
        await process_user_request(callback.message, "маржа")
    elif action == "china":
        await process_user_request(callback.message, "китай")
    elif action == "smysly":
        await process_user_request(callback.message, "смыслы")
    elif action == "praktikum":
        await process_user_request(callback.message, "практикум")


@dp.message(F.text.lower().contains("старт"))
async def handle_text_start(message: types.Message):
    await process_user_request(message, "старт")


@dp.message(F.text.lower().contains("маржа"))
async def handle_text_marzha(message: types.Message):
    await process_user_request(message, "маржа")


@dp.message(F.text.lower().contains("китай"))
async def handle_text_china(message: types.Message):
    await process_user_request(message, "китай")


@dp.message(F.text.lower().contains("смыслы"))
async def handle_text_smysly(message: types.Message):
    await process_user_request(message, "смыслы")


@dp.message(F.text.lower().contains("практикум"))
async def handle_text_praktikum(message: types.Message):
    await process_user_request(message, "практикум")


@dp.callback_query(F.data.startswith("check_sub_"))
async def process_sub_check(callback: types.CallbackQuery):
    keyword = callback.data.replace("check_sub_", "")
    is_subbed = await check_subscription(callback.from_user.id)
    if is_subbed:
        await callback.answer("✅ Подписка подтверждена!")
        await callback.message.delete()
        await process_user_request(callback.message, keyword)
    else:
        await callback.answer(
            "❌ Вы еще не подписались на канал!", show_alert=True
        )


@dp.callback_query(F.data.startswith("lesson_"))
async def process_lesson_callback(callback: types.CallbackQuery):
    lesson_num = int(callback.data.split("_")[1])
    await callback.answer()
    await send_lesson(callback.message.chat.id, lesson_num)


# --- АДМИН-ПАНЕЛЬ ---
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT segment, COUNT(*) FROM users GROUP BY segment"
        ) as cursor:
            segments = await cursor.fetchall()

    stat_text = f"📊 **СТАТИСТИКА БОТА:**\n\nВсего пользователей: **{total_users}**\n\nПо сегментам:\n"
    for seg, count in segments:
        stat_text += f"• `{seg}`: {count}\n"
    await message.answer(stat_text, parse_mode="Markdown")


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "✏️ Отправьте сообщение, которое нужно разослать всем пользователям бота:"
    )
    await state.set_state(BroadcastState.waiting_for_message)


@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🚀 Начинаю рассылку...")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()

    count = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Рассылка завершена! Доставлено: **{count}** пользователям.")


# --- ЗАПУСК ---
async def main():
    await init_db()
    logging.info("Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())