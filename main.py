import os
import requests
import sqlite3
import logging
import asyncio
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from textblob import TextBlob
from datetime import datetime
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split

# ENV VARS
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# BOT DB
conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS fiyatlar (
  tarih TEXT, altin REAL, usd REAL, haber_puani REAL
)
""")
conn.commit()

# Veri çekme ve tahmin
def veri_guncelle():
    try:
        # Altın ve USD verilerini al
        altin = float(requests.get("https://api.exchangerate.host/latest?base=TRY&symbols=XAU").json()["rates"]["XAU"])
        usd = float(requests.get("https://api.exchangerate.host/latest?base=TRY&symbols=USD").json()["rates"]["USD"])

        # Haber puanı hesapla
        metin = requests.get("https://www.bloomberg.com/markets/economics").text
        haber_puani = TextBlob(metin).sentiment.polarity

        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO fiyatlar VALUES (?, ?, ?, ?)", (tarih, altin, usd, haber_puani))
        conn.commit()
        logging.info(f"Veri alındı: Altın={altin}, USD={usd}, Haber={haber_puani:.2f}")

        model_tahmin()
    except Exception as e:
        logging.error(f"Veri çekme hatası: {e}")

def model_tahmin():
    df = pd.read_sql_query("SELECT * FROM fiyatlar", conn)
    if len(df) < 20:
        return

    df['tarih'] = pd.to_datetime(df['tarih'])
    df.sort_values('tarih', inplace=True)
    df['altin_gelecek'] = df['altin'].shift(-1)
    df.dropna(inplace=True)

    X = df[['altin', 'usd', 'haber_puani']]
    y = df['altin_gelecek']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = XGBRegressor()
    model.fit(X_train, y_train)
    pred = model.predict([X.iloc[-1]])[0]
    son = df['altin'].iloc[-1]

    if pred > son * 1.01:
        mesaj = f"📈 Altın artabilir. Tahmin: {pred:.2f}"
    elif pred < son * 0.99:
        mesaj = f"📉 Altın düşebilir. Tahmin: {pred:.2f}"
    else:
        mesaj = None

    if mesaj:
        try:
            import telegram
            bot = telegram.Bot(token=BOT_TOKEN)
            bot.send_message(chat_id=CHAT_ID, text=mesaj)
        except Exception as e:
            logging.error(f"Telegram mesaj hatası: {e}")

# /durum komutu
async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    mesaj = (
        f"📊 Son Veri\nTarih: {row[0]}\nAltın: {row[1]}\nUSD: {row[2]}\nHaber Puanı: {row[3]:.2f}"
        if row else "Veri bulunamadı."
    )
    await update.message.reply_text(mesaj)

# Telegram bot başlat
async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", durum))
    await app.run_polling()

# Flask sunucusu
web_app = Flask(__name__)
@web_app.route("/")
def home():
    return "Bot çalışıyor."

# Zamanlayıcı başlat
scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
scheduler.add_job(veri_guncelle, "interval", minutes=5)
scheduler.start()

# Main: Flask ve bot aynı anda
async def main():
    bot_task = asyncio.create_task(start_bot())
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: web_app.run(host="0.0.0.0", port=5000))
    await bot_task

if __name__ == "__main__":
    asyncio.run(main())
