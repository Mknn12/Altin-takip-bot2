import os
import sqlite3
import logging
from flask import Flask
import asyncio
import threading

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükle

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env dosyasında tanımlı değil!")

# Veritabanı ayarları
conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS fiyatlar (
    tarih TEXT,
    altin REAL,
    usd REAL,
    haber_puani REAL
)
""")
conn.commit()

# /durum komutu
async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    if row:
        mesaj = f"📊 Son Veri\nTarih: {row[0]}\nAltın: {row[1]}\nUSD: {row[2]}\nHaber Puanı: {row[3]:.2f}"
    else:
        mesaj = "Veri bulunamadı."
    await update.message.reply_text(mesaj)

# Telegram botunu başlatan fonksiyon
async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", durum))
    print("✅ Telegram botu başlatıldı")
    await app.run_polling()

# Flask app
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot çalışıyor."

def run_flask():
    web_app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    # Flask'ı ayrı thread'de başlat
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Telegram botu ana thread'de asyncio ile başlat
    asyncio.run(start_bot())
