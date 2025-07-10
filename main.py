import os
import time
import logging
import requests
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, Filters, MessageHandler
from threading import Thread

load_dotenv()

# API KEYLERİ
FMP_API_KEY = os.getenv("FMP_API_KEY")  # Financial Modeling Prep
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# ---- Fiyatları çekme fonksiyonları ----
def get_gold_price():
    url = f"https://financialmodelingprep.com/api/v3/quote/GC=F?apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            price = data[0].get('price')
            return price
        else:
            logger.error("Altın fiyatı verisi boş veya hatalı formatta")
            return None
    except Exception as e:
        logger.error(f"Altın fiyatı çekme hatası: {e}")
        return None

def get_usd_try():
    url = f"https://financialmodelingprep.com/api/v3/quote/USDTRY=X?apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            price = data[0].get('price')
            return price
        else:
            logger.error("USD/TRY kuru verisi boş veya hatalı formatta")
            return None
    except Exception as e:
        logger.error(f"USD/TRY kuru çekme hatası: {e}")
        return None

# ---- Haberleri çekme fonksiyonu (GNews API, günlük 100 istek limitli) ----
def get_news(query="altın", max_articles=5):
    url = f"https://gnews.io/api/v4/search?q={query}&token={GNEWS_API_KEY}&lang=tr&max={max_articles}"
    try:
        resp = requests.get(url)
        data = resp.json()
        if data.get("articles"):
            articles = data["articles"]
            return articles
        else:
            logger.error("Haber verisi boş veya hatalı formatta")
            return []
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
        return []

# ---- Telegram komutları ----
def durum(update, context):
    gold_price = get_gold_price()
    usd_try = get_usd_try()

    if gold_price is None or usd_try is None:
        text = "Fiyat bilgileri alınamadı."
    else:
        text = (f"Gram Altın: {gold_price:.2f} USD\n"
                f"USD/TRY: {usd_try:.4f} TL\n")

    update.message.reply_text(text)

def start(update, context):
    update.message.reply_text(
        "Merhaba! /durum komutuyla güncel fiyatları görebilirsin."
    )

# ---- Flask ve Telegram Bot entegrasyonu ----
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

# ---- Telegram bot dispatcher ayarı ----
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("durum", durum))

# ---- Main döngü (Render veya başka sunucuda 12 saatlik çalışmaya uygun) ----
def main():
    # Flask web sunucusunu thread olarak başlat
    Thread(target=run_flask).start()

    # Buraya ileride fiyat takibi ve fırsat varsa Telegram'a bildirme kodu eklenebilir
    while True:
        time.sleep(3600)  # Saatte bir bekle (veya ihtiyaca göre değiştir)
        # Fiyat ve fırsat kontrolü yapılabilir

if __name__ == "__main__":
    main()
