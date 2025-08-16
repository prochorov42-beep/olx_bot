import asyncio
import sqlite3
import requests
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message

# 🔑 Токен бота
TOKEN = "8065536116:AAGx8RetEX2sPeisD3yUpTKFNzEe-gJ6FmI"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 🔗 Ссылки OLX для Wrocław
URLS = {
    "обычные": "https://www.olx.pl/sport-hobby/rowery/wroclaw/?min_id=1020411554&reason=observed_search&search%5Border%5D=created_at%3Adesc",
    "электро": "https://www.olx.pl/sport-hobby/rowery/rowery-elektryczne/wroclaw/?min_id=1019981074&reason=observed_search&search%5Border%5D=created_at%3Adesc"
}

# 🔢 Лимиты цены
MAX_PRICE = {
    "обычные": 250,
    "электро": 1300
}

# 📂 База данных для отслеживания объявлений
conn = sqlite3.connect("ads.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS sent_ads (ad_id TEXT PRIMARY KEY)")
conn.commit()

# ⌨️ Клавиатура
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚲 Обычные"), KeyboardButton(text="⚡ Электро")],
        [KeyboardButton(text="▶️ Пуск"), KeyboardButton(text="⏸ Пауза"), KeyboardButton(text="⛔ Стоп")]
    ],
    resize_keyboard=True
)

# 👤 Состояние подписки пользователей
user_subscribed = {}


# 📡 Функция парсинга OLX
async def fetch_ads(category):
    url = URLS[category]
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    ads = []
    for item in soup.select("div.offer-wrapper"):
        try:
            title = item.select_one("strong").text.strip()
            link = item.select_one("a")["href"]
            price_text = item.select_one(".price").text.strip().replace("zł", "").replace(" ", "")
            price = int(price_text)
            ad_id = link.split("/")[-1]
            if price <= MAX_PRICE[category]:
                ads.append((ad_id, title, link, price))
        except:
            continue
    return ads


# ✉️ Отправка новых объявлений
async def send_new_ads(user_id, category):
    ads = await fetch_ads(category)
    for ad_id, title, link, price in ads:
        c.execute("SELECT 1 FROM sent_ads WHERE ad_id=?", (ad_id,))
        if not c.fetchone():
            await bot.send_message(user_id, f"{title}\n{price} zł\n{link}")
            c.execute("INSERT INTO sent_ads (ad_id) VALUES (?)", (ad_id,))
            conn.commit()


# 🔄 Цикл проверки объявлений
async def check_ads():
    while True:
        for user_id, categories in user_subscribed.items():
            for category in categories:
                await send_new_ads(user_id, category)
        await asyncio.sleep(60)  # каждые 1 минуту


# ================== ХЕНДЛЕРЫ ==================

@dp.message(Command("start"))
async def start_handler(message: Message):
    user_subscribed[message.from_user.id] = []
    await message.answer("Привет! 🚀\nВыберите категорию:", reply_markup=keyboard)


@dp.message(F.text.in_(["🚲 Обычные", "⚡ Электро"]))
async def category_handler(message: Message):
    user_id = message.from_user.id
    category = "обычные" if message.text == "🚲 Обычные" else "электро"

    if user_id not in user_subscribed:
        user_subscribed[user_id] = []
    if category not in user_subscribed[user_id]:
        user_subscribed[user_id].append(category)

    await message.answer(f"✅ Подписка на {category} активирована.")


@dp.message(F.text.in_(["▶️ Пуск", "⏸ Пауза", "⛔ Стоп"]))
async def control_handler(message: Message):
    user_id = message.from_user.id
    text = message.text

    if text == "▶️ Пуск":
        if user_id not in user_subscribed:
            user_subscribed[user_id] = []
        await message.answer("▶️ Уведомления включены.")

    elif text == "⏸ Пауза":
        user_subscribed[user_id] = []
        await message.answer("⏸ Уведомления приостановлены.")

    elif text == "⛔ Стоп":
        if user_id in user_subscribed:
            del user_subscribed[user_id]
        await message.answer("⛔ Подписка полностью остановлена.")


# 🚀 Запуск бота
async def main():
    asyncio.create_task(check_ads())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



