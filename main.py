import os
import requests
import sqlite3
import logging
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from textblob import TextBlob
from datetime import datetime
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
import asyncio
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)
conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS fiyatlar (
  tarih TEXT, altin REAL, usd REAL, haber_puani REAL
)
""")
conn.commit()

def veri_guncelle():
    try:
        # exchangerate.host altın ve usd kuru
        response = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=TRY,XAU")
        data = response.json()
        usd_try = data["rates"]["TRY"]
        # altın ons fiyatı XAU/USD için, TRY'ye çevirmek gerek: ons * usd_try
        xau_usd_response = requests.get("https://api.exchangerate.host/convert?from=XAU&to=USD")
        xau_usd = xau_usd_response.json().get("result", 1900)  # fallback varsayılan 1900 USD/onça
        altin = xau_usd * usd_try

        # Haber puanı için örnek Bloomberg sayfası metni
        metin = requests.get("https://www.bloomberg.com/markets/economics").text
        haber_puani = TextBlob(metin).sentiment.polarity

        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO fiyatlar VALUES (?, ?, ?, ?)", (tarih, altin, usd_try, haber_puani))
        conn.commit()
        logging.info(f"Veri alindi: Altın={altin:.2f}, USD/TRY={usd_try:.2f}, Haber puanı={haber_puani:.2f}")
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
        asyncio.run(bot.send_message(chat_id=CHAT_ID, text=f"📈 Altın artabilir. Tahmin: {pred:.2f}"))
    elif pred < son * 0.99:
        asyncio.run(bot.send_message(chat_id=CHAT_ID, text=f"📉 Altın düşebilir. Tahmin: {pred:.2f}"))

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    if row:
        mesaj = f"📊 Son Veri\nTarih: {row[0]}\nAltın: {row[1]:.2f} TRY\nUSD/TRY: {row[2]:.2f}\nHaber Puanı: {row[3]:.2f}"
    else:
        mesaj = "Veri bulunamadı."
    await update.message.reply_text(mesaj)

async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", durum))
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
scheduler.add_job(veri_guncelle, "interval", minutes=5)
scheduler.start()

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot çalışıyor."

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000)

if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(start_bot())
