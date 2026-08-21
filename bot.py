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


# --- ОДНОКНОПОЧНЫЕ КЛАВИАТУРЫ ДЛЯ ВЕТОК (СТРОГО 1 КНОПКА) ---
def get_nisha_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Посмотреть практикум «Маржинальные ниши»",
                    url=URL_NISHA,
                )
            ]
        ]
    )


def get_china_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Посмотреть практикум «Закупки в Китае & 1688»",
                    url=URL_CHINA,
                )
            ]
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
            ]
        ]
    )


def get_bundle_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Забронировать Бандл 3-в-1 со скидкой 30%",
                    url=URL_BUNDLE,
                )
            ]
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


# --- ИНДИВИДУАЛЬНЫЕ АВТОДОГРЕВЫ ДО БАНДЛА (ЧЕРЕЗ 24 ЧАСА) ---
async def schedule_bundle_upsell(chat_id: int, branch: str):
    await asyncio.sleep(86400)  # 24 часа

    upsell_messages = {
        "marzha": (
            "📊 <b>Вчера вы забирали Калькулятор и гайд по Узким Нишам.</b>\n\n"
            "Выбрать идеальную нишу — это важный первый шаг. Но если у вас нет прямого дешевого импорта из Китая и смысловой упаковки карточки, конкуренты быстро сожмут вашу маржу.\n\n"
            "Товарный бизнес 2026 года — это **Треугольник Успеха**:\n"
            "1️⃣ Маржинальная узкая ниша\n"
            "2️⃣ Прямой импорт без перекупщиков\n"
            "3️⃣ Продающая смысловая упаковка\n\n"
            "Заберите **Полный Бандл из 3-х Практикумов Елены Тимошенко**, чтобы выстроить всю систему под ключ со скидкой 30%!"
        ),
        "china": (
            "🇨🇳 <b>Вчера вы забирали гайды по закупкам в Китае.</b>\n\n"
            "Выгодный закуп на 1688 — это мощный рычаг. Но если товар выбран в перегретой нише без маржи, или карточка упакована «как у всех» — товар застрянет на складе.\n\n"
            "Закройте все 3 элемента **Треугольника Успеха** (Ниша + Импорт + Смыслы) одновременно!\n\n"
            "Заберите **Полный Бандл из 3-х Практикумов Елены Тимошенко** и стройте системный бизнес со скидкой 30%!"
        ),
        "smysly": (
            "🧠 <b>Вчера вы забирали гайды по Продающим Смыслам.</b>\n\n"
            "Сильный оффер поднимает конверсию в 2–3 раза. Но если продукт изначально выбран без математики маржинальности, а закупки идут через дорогих перекупщиков — высокой прибыли не будет.\n\n"
            "Соедините Смыслы с Нишей и Прямым Импортом в единый **Треугольник Успеха**!\n\n"
            "Заберите **Полный Бандл из 3-х Практикумов Елены Тимошенко** со скидкой 30%!"
        ),
    }

    text = upsell_messages.get(branch)
    if text:
        try:
            await bot.send_message(
                chat_id,
                text,
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
            "Чтобы построить системный бизнес под ключ без ошибок — заберите **Полный Бандл из 3-х Практикумов Елены Тимошенко** со специальной скидкой 30%!",
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
                        text="📢 Подписаться на канал",
                        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Я подписался, проверить",
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
    if keyword in ["старт", "start"]:
        await message.answer(
            "👋 **Приветствую!** Рада видеть вас на бесплатном Тест-Драйве Товарного Бизнеса 2026!",
            parse_mode="Markdown",
        )
        await send_lesson(message.chat.id, 1)

    elif keyword == "маржа":
        await message.answer(
            "📊 **Выдаю материалы по Юнит-Экономике и Узким Нишам:**",
            parse_mode="Markdown",
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

        # Сильное дожимное сообщение
        warmup_text = (
            "💡 **Слабый товар сливает бюджет еще до старта.**\n\n"
            "Очень часто селлеры выбирают нишу на эмоциях: *«у других же продается»*, *«кажется перспективным»*. "
            "А в итоге сталкиваются с жестким демпингом, дорогой рекламой и отсутствием чистой прибыли. **Деньги теряют не на идеях, а на выборе вслепую без системы.**\n\n"
            "На практикуме **«Золотая Ниша»** вы за 11 уроков пройдете путь от поиска идей до точного выбора:\n\n"
            "🔹 **5 стратегий поиска** прибыльных и узких ниш\n"
            "🔹 **Оценка спроса и конкуренции:** как не зайти туда, где вас раздавят гиганты\n"
            "🔹 **Математика маржинальности:** сравнение вариантов строго по цифрам\n"
            "🔹 **Результат:** готовая система и таблица оценки ниш для выбора с холодной головой\n\n"
            "🎓 *Автор курса:* **Елена Тимошенко** — дипломированный маркетолог, эксперт e-Commerce с 2007 года.\n\n"
            "👇 **Нажмите кнопку ниже, чтобы посмотреть практикум и забрать систему оценки ниш:**"
        )
        await message.answer(
            warmup_text,
            parse_mode="Markdown",
            reply_markup=get_nisha_keyboard(),
        )
        asyncio.create_task(schedule_bundle_upsell(message.chat.id, "marzha"))

    elif keyword == "китай":
        await message.answer(
            "🇨🇳 **Выдаю материалы по Закупкам и Логистике в Китае:**",
            parse_mode="Markdown",
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

        # Сильное дожимное сообщение
        warmup_text = (
            "💡 **Как научиться закупать товары напрямую на фабриках за 1 вечер — даже без знания китайского языка?**\n\n"
            "Вы получили гайд, но чтобы начать реальные закупки, нужно закрыть ключевые технические вопросы: **как зарегистрировать Alipay, как общаться с поставщиками без знания языка, как оплачивать и не потерять груз на таможне.**\n\n"
            "На онлайн-курсе **«Закупки в Китае и РФ с нуля»** вы получите пошаговые наглядные видео-инструкции:\n\n"
            "🔹 **Разбор 5 главных площадок:** 1688, Taobao, Pinduoduo, Dewu (бренды со скидкой до 70%) и Alibaba\n"
            "🔹 **Практика:** Пошаговая регистрация кошелька **Alipay** и аккаунтов на фабриках\n"
            "🔹 **Контакты и Брони:** База проверенных посредников в Китае + готовые скрипты общения\n"
            "🔹 **Альтернатива:** Готовая база поставщиков в России — для старта без ожидания логистики!\n\n"
            "🎓 *Автор курса:* **Елена Тимошенко** — эксперт e-Commerce с опытом с 2007 года (протестировано 1000+ товаров).\n\n"
            "👇 **Нажмите кнопку ниже, чтобы посмотреть программу и получить доступ ко всем базам:**"
        )
        await message.answer(
            warmup_text,
            parse_mode="Markdown",
            reply_markup=get_china_keyboard(),
        )
        asyncio.create_task(schedule_bundle_upsell(message.chat.id, "china"))

    elif keyword == "смыслы":
        await message.answer(
            "🧠 **Выдаю материалы по Продающим Смыслам и Упаковке:**",
            parse_mode="Markdown",
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

        # Сильное дожимное сообщение
        warmup_text = (
            "💡 **В 2026 году продает не товар, а смысловая упаковка!**\n\n"
            "Можно найти идеальную нишу и привезти товар из Китая, но если ваша карточка на МП, Авито или в соцсетях выглядит как у всех — вам придется снижать цену и работать в убыток.\n\n"
            "**Продающие смыслы** — это единственное, что позволяет продавать **ДОРОЖЕ рынка** и не сливать бюджет на безумную рекламу.\n\n"
            "На практикуме **«Продающие Смыслы & Упаковка»** от **Елены Тимошенко** вы получите:\n\n"
            "🔹 **Конструктор офферов:** как находить истинные боли покупателей и закрывать их в визуале\n"
            "🔹 **Отстройку от конкурентов:** как выделять товар среди сотен аналогичных\n"
            "🔹 **Рост конверсии в 2–3 раза:** превращение кликов и просмотров в реальные оплаты\n\n"
            "💎 Перестаньте отдавать свою маржу демпингующим конкурентам — заставьте клиентов влюбляться в ваш продукт!\n\n"
            "👇 **Посмотреть практикум прямо сейчас:**"
        )
        await message.answer(
            warmup_text,
            parse_mode="Markdown",
            reply_markup=get_smysly_keyboard(),
        )
        asyncio.create_task(schedule_bundle_upsell(message.chat.id, "smysly"))


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
    elif args in ["start_course", "start"]:
        await process_user_request(message, "старт")
        return

    welcome_menu_text = (
        "👋 **Добро пожаловать в бот экспертного маркетинга в e-Commerce!**\n\n"
        "Выберите направление, которое вас интересует, нажав на кнопку ниже:\n\n"
        "P.S. Этот бот не собирает и не хранит Ваши личные данные"
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