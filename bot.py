import asyncio
import os
import aiosqlite
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from bs4 import BeautifulSoup

# Получаем токен из переменной окружения
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Токен не найден! Установи переменную окружения TOKEN.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Ссылки OLX для Wrocław
URLS = {
    "обычные": "https://www.olx.pl/d/rowery/q-rower/?search%5Bfilter_enum_city%5D%5B0%5D=wroclaw",
    "электро": "https://www.olx.pl/d/rowery/q-rower-elektryczny/?search%5Bfilter_enum_city%5D%5B0%5D=wroclaw"
}

MAX_PRICE = {
    "обычные": 250,
    "электро": 1300
}

# Клавиатура
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚲 Обычные"), KeyboardButton(text="⚡ Электро")],
        [KeyboardButton(text="▶️ Пуск"), KeyboardButton(text="⏸ Пауза"), KeyboardButton(text="⛔ Стоп")]
    ],
    resize_keyboard=True
)

# Состояние подписки пользователей
user_subscribed = {}

# ---------------------------
# Асинхронная работа с базой
# ---------------------------
DB_PATH = "ads.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS sent_ads (ad_id TEXT PRIMARY KEY)")
        await db.commit()

async def ad_exists(ad_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM sent_ads WHERE ad_id=?", (ad_id,)) as cursor:
            return await cursor.fetchone() is not None

async def save_ad(ad_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO sent_ads (ad_id) VALUES (?)", (ad_id,))
        await db.commit()

# ---------------------------
# Получение объявлений
# ---------------------------
async def fetch_ads(category):
    url = URLS[category]
    ads = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            text = await r.text()
    soup = BeautifulSoup(text, "html.parser")
    for item in soup.select("div.offer-wrapper"):
        try:
            title = item.select_one("strong").text.strip()
            link = item.select_one("a")["href"]
            price_text = item.select_one(".price").text.strip().replace("zł", "").replace(" ", "")
            try:
                price = int(price_text)
            except ValueError:
                continue  # пропускаем объявления без цены
            ad_id = link.split("/")[-1]
            if price <= MAX_PRICE[category]:
                ads.append((ad_id, title, link, price))
        except:
            continue
    return ads

async def send_new_ads(user_id, category):
    ads = await fetch_ads(category)
    for ad_id, title, link, price in ads:
        if not await ad_exists(ad_id):
            await bot.send_message(user_id, f"{title}\n{price} zł\n{link}")
            await save_ad(ad_id)

# ---------------------------
# Проверка объявлений в фоне
# ---------------------------
async def check_ads():
    while True:
        for user_id, categories in user_subscribed.items():
            for category in categories:
                await send_new_ads(user_id, category)
        await asyncio.sleep(60)  # Проверка каждую минуту

# ---------------------------
# Хендлеры
# ---------------------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id
    user_subscribed[user_id] = []
    await message.answer("Выберите категорию:", reply_markup=keyboard)

@dp.message_handler()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if text in ["🚲 Обычные", "⚡ Электро"]:
        category = "обычные" if text == "🚲 Обычные" else "электро"
        if user_id not in user_subscribed:
            user_subscribed[user_id] = []
        if category not in user_subscribed[user_id]:
            user_subscribed[user_id].append(category)
        await message.answer(f"Подписка на {category} активирована.")

    elif text in ["▶️ Пуск", "⏸ Пауза", "⛔ Стоп"]:
        if text == "▶️ Пуск":
            if user_id not in user_subscribed:
                user_subscribed[user_id] = []
            await message.answer("Уведомления включены.")
        elif text == "⏸ Пауза":
            user_subscribed[user_id] = []
            await message.answer("Уведомления приостановлены.")
        elif text == "⛔ Стоп":
            if user_id in user_subscribed:
                del user_subscribed[user_id]
            await message.answer("Подписка полностью остановлена.")

# ---------------------------
# Запуск бота
# ---------------------------
async def main():
    await init_db()
    asyncio.create_task(check_ads())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


