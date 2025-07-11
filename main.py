import os
import sqlite3
import logging
import threading

from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import nest_asyncio
import asyncio

# Gerekiyorsa mevcut event loop'a izin ver
nest_asyncio.apply()

# Ortam değişkenlerini yükle
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env dosyasında tanımlı değil!")

# Veritabanı bağlantısı
conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()

# Tabloyu oluştur
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
        mesaj = f"📊 Son Veri\nTarih: {row[0]}\nAltın: {row[1]}₺\nUSD: {row[2]}₺\nHaber Puanı: {row[3]:.2f}"
    else:
        mesaj = "Veri bulunamadı."
    await update.message.reply_text(mesaj)

# Telegram botu
async def start_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("durum", durum))
    print("✅ Telegram botu başlatıldı")
    await application.run_polling()

# Flask sunucusu
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot çalışıyor."

# Flask'ı ayrı threadde çalıştır
def run_flask():
    web_app.run(host="0.0.0.0", port=5000)

# Ana giriş noktası
def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
