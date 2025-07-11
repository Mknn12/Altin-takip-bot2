import os
import sqlite3
from flask import Flask
import asyncio
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env dosyasında tanımlı değil!")

# Veritabanı bağlantısı (thread-safe)
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

def main():
    # Flask'ı ayrı thread'de başlat
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Telegram botu için event loop varsa onu kullan, yoksa yeni yarat
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Eğer event loop zaten çalışıyorsa, botu bu loop ile çalıştır
        asyncio.ensure_future(start_bot())
        # Ana thread sonsuz döngüde kalsın ki program kapanmasın
        loop.run_forever()
    else:
        # Event loop yoksa normal şekilde başlat
        asyncio.run(start_bot())

if __name__ == "__main__":
    main()
