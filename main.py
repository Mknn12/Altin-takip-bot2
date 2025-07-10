# main.py
import os
import requests
import sqlite3
import logging
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot, Update
from telegram.ext import CommandHandler, Updater, CallbackContext
from textblob import TextBlob
from datetime import datetime
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from bs4 import BeautifulSoup

# Ortam degiskenleri
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FMP_API_KEY = os.getenv("FMP_API_KEY")

# Telegram bot ayar
bot = Bot(token=BOT_TOKEN)

# Veritabani baglantisi
conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS fiyatlar (
    tarih TEXT,
    altin REAL,
    usd REAL,
    haber_puani REAL
)''')
conn.commit()

# Flask sunucusu
app = Flask(__name__)

# Logger
logging.basicConfig(level=logging.INFO)

# Veri cekme
def veri_guncelle():
    try:
        altin = requests.get(f"https://financialmodelingprep.com/api/v3/quote/GCUSD?apikey={FMP_API_KEY}").json()[0]['price']
        usd = requests.get(f"https://financialmodelingprep.com/api/v3/fx/USD/TRY?apikey={FMP_API_KEY}").json()['to']
        haberler = requests.get("https://www.bloomberg.com/markets/economics").text
        soup = BeautifulSoup(haberler, 'lxml')
        metin = ' '.join([p.text for p in soup.find_all('p')])
        haber_puani = TextBlob(metin).sentiment.polarity

        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO fiyatlar VALUES (?, ?, ?, ?)", (tarih, altin, usd, haber_puani))
        conn.commit()

        logging.info(f"Veri alindi: {tarih} Altin: {altin}, USD: {usd}, Haber: {haber_puani}")

        model_tahmin()

    except Exception as e:
        logging.error(f"Veri cekme hatasi: {e}")

# ML tahmin
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

    gelecek_tahmin = model.predict([X.iloc[-1]])[0]
    logging.info(f"Tahmin edilen altin: {gelecek_tahmin:.2f}")

    if gelecek_tahmin > df['altin'].iloc[-1] * 1.01:
        bot.send_message(chat_id=CHAT_ID, text=f"📈 Altin yukselecek gibi görünüyor! Tahmin: {gelecek_tahmin:.2f}")
    elif gelecek_tahmin < df['altin'].iloc[-1] * 0.99:
        bot.send_message(chat_id=CHAT_ID, text=f"📉 Altin dusme sinyali verdi! Tahmin: {gelecek_tahmin:.2f}")

# /durum komutu

def durum(update: Update, context: CallbackContext):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    if row:
        mesaj = f"📊 Son Veri\nTarih: {row[0]}\nAltin: {row[1]}\nUSD: {row[2]}\nHaber Puani: {row[3]:.2f}"
    else:
        mesaj = "Veri bulunamadi."
    update.message.reply_text(mesaj)

# Bot dispatcher
updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(CommandHandler("durum", durum))
updater.start_polling()

# Scheduler başlat
scheduler = BackgroundScheduler()
scheduler.add_job(veri_guncelle, "interval", minutes=5)
scheduler.start()

# Flask endpoint
@app.route("/")
def home():
    return "Bot calisiyor."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
