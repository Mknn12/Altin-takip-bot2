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

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS fiyatlar (
  tarih TEXT, altin REAL, usd TRY REAL, haber_puani REAL
)
""")
conn.commit()

def veri_guncelle():
    try:
        # Döviz kuru (USD/TRY)
        kur_res = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=TRY")
        kur_res.raise_for_status()
        usd_try = kur_res.json()["rates"]["TRY"]

        # Altın fiyatı: Genelde ons altın fiyatı dolar cinsindendir (burada sabit örnek veriyorum)
        # Güncel altın fiyatını farklı API'den ya da sabit örnek ile gösterebiliriz:
        # Örnek: ons altın fiyatı 1950 USD varsayalım (güncelle istersen)
        ons_altin_usd = 1950.0

        # Gram altın fiyatı (yaklaşık): 1 ons = 31.1035 gram
        altin_gram_try = (ons_altin_usd / 31.1035) * usd_try

        # Haber metni çek (örnek)
        metin = requests.get("https://www.bloomberg.com/markets/economics").text
        haber_puani = TextBlob(metin).sentiment.polarity

        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO fiyatlar VALUES (?, ?, ?, ?)", (tarih, altin_gram_try, usd_try, haber_puani))
        conn.commit()

        logging.info(f"Veri alindi: Altın (TRY)={altin_gram_try:.2f}, USD/TRY={usd_try:.2f}, Haber puanı={haber_puani:.2f}")
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

    X = df[['altin', 'usd TRY', 'haber_puani']]
    y = df['altin_gelecek']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = XGBRegressor()
    model.fit(X_train, y_train)

    pred = model.predict([X.iloc[-1]])[0]
    son = df['altin'].iloc[-1]

    if pred > son * 1.01:
        bot.send_message(chat_id=CHAT_ID, text=f"📈 Altın artabilir. Tahmin: {pred:.2f} TRY")
    elif pred < son * 0.99:
        bot.send_message(chat_id=CHAT_ID, text=f"📉 Altın düşebilir. Tahmin: {pred:.2f} TRY")

def durum(update: Update, context: CallbackContext):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    mesaj = f"📊 Son Veri\nTarih: {row[0]}\nAltın (TRY): {row[1]:.2f}\nUSD/TRY: {row[2]:.2f}\nHaber Puanı: {row[3]:.2f}" if row else "Veri bulunamadı."
    update.message.reply_text(mesaj)

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(CommandHandler("durum", durum))
updater.start_polling()

scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
scheduler.add_job(veri_guncelle, "interval", minutes=5)
scheduler.start()

app = Flask(__name__)
@app.route("/")
def home():
    return "Bot çalışıyor."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
