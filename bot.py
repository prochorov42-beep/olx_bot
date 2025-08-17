import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import aiohttp
from bs4 import BeautifulSoup

# Токен из переменной окружения
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

# База данных
conn = sqlite3.connect("ads.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS sent_ads (ad_id TEXT PRIMARY KEY)")
conn.commit()

# Клавиатура
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚲 Обычные"), KeyboardButton(text="⚡ Электро")],
        [KeyboardButton(text="▶️ Пуск"), KeyboardButton(text="⏸ Пауза"), KeyboardButton(text="⛔ Стоп")]
    ],
    resize_keyboard=True
)

# Состояние подписки
user_subscribed = {}

# --- Парсер OLX ---
async def fetch_ads(category):
    url = URLS[category]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ads = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")

            for link_tag in soup.select("a[href*='/oferta/']"):
                try:
                    link = link_tag["href"]

                    # Заголовок
                    title_tag = link_tag.select_one("h6")
                    if not title_tag:
                        title_tag = link_tag.get("title")
                    if not title_tag:
                        continue
                    title = title_tag.text.strip() if hasattr(title_tag, "text") else title_tag.strip()

                    # Цена
                    price_tag = link_tag.select_one("p")
                    if not price_tag:
                        continue
                    price_text = price_tag.text.strip().replace("zł", "").replace(" ", "").replace(",", "")
                    price = int(''.join(filter(str.isdigit, price_text)))

                    if price > MAX_PRICE[category]:
                        continue

                    ad_id = link.split("/")[-2]  # ID объявления
                    ads.append((ad_id, title, link, price))
                except:
                    continue
    return ads

# --- Отправка новых объявлений (с сортировкой по цене) ---
async def send_new_ads(user_id, category):
    ads = await fetch_ads(category)
    # Сортировка по цене от меньшей к большей
    ads.sort(key=lambda x: x[3])
    for ad_id, title, link, price in ads:
        c.execute("SELECT 1 FROM sent_ads WHERE ad_id=?", (ad_id,))
        if not c.fetchone():
            await bot.send_message(user_id, f"{title}\n{price} zł\n{link}")
            c.execute("INSERT INTO sent_ads (ad_id) VALUES (?)", (ad_id,))
            conn.commit()

# --- Проверка новых объявлений каждые 60 секунд ---
async def check_ads():
    while True:
        for user_id, categories in user_subscribed.items():
            for category in categories:
                await send_new_ads(user_id, category)
        await asyncio.sleep(60)

# --- Хендлер /start ---
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    user_subscribed[user_id] = []
    await message.answer("Выберите категорию:", reply_markup=keyboard)

dp.message.register(start_handler, F.text == "/start")

# --- Хендлер кнопок ---
async def button_handler(message: types.Message):
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

dp.message.register(button_handler)

# --- Запуск бота ---
async def main():
    asyncio.create_task(check_ads())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

