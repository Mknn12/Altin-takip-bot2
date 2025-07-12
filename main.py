import os
import sqlite3
import logging
from flask import Flask
import threading
import asyncio
import datetime
import requests
from textblob import TextBlob
from sklearn.linear_model import LinearRegression
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Ortam değişkenlerini yükle
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")  # Financial Modeling Prep API Key

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env dosyasında tanımlı değil!")

# Veritabanı kurulumu
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

# Haber puanı analizi
def haber_puani_getir():
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers=GLD&limit=5&apikey={API_KEY}"
        response = requests.get(url)
        haberler = response.json()
        puanlar = []
        for haber in haberler:
            blob = TextBlob(haber['title'] + ". " + haber['text'])
            puanlar.append(blob.sentiment.polarity)
        return round(sum(puanlar)/len(puanlar), 3) if puanlar else 0.0
    except Exception as e:
        print("Haber puanı hatası:", e)
        return 0.0

# Fiyat verisini API'den çek
def veri_cek():
    try:
        altin_url = f"https://financialmodelingprep.com/api/v3/quote/GCUSD?apikey={API_KEY}"
        usd_url = f"https://financialmodelingprep.com/api/v3/fx/USDTry?apikey={API_KEY}"

        altin = requests.get(altin_url).json()[0]['price']
        usd = requests.get(usd_url).json()[0]['price']
        puan = haber_puani_getir()
        tarih = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        c.execute("INSERT INTO fiyatlar VALUES (?, ?, ?, ?)", (tarih, altin, usd, puan))
        conn.commit()

        print(f"✅ Veri eklendi: {tarih} | Altın: {altin}, USD: {usd}, Puan: {puan}")
        return altin, usd, puan
    except Exception as e:
        print("Veri çekme hatası:", e)
        return None, None, None

# ML tahmini
def altin_tahmini():
    c.execute("SELECT rowid, altin FROM fiyatlar ORDER BY rowid DESC LIMIT 10")
    rows = c.fetchall()[::-1]  # eski -> yeni
    if len(rows) < 5:
        return None
    X = np.array([r[0] for r in rows]).reshape(-1, 1)
    y = np.array([r[1] for r in rows])
    model = LinearRegression().fit(X, y)
    gelecek = model.predict(np.array([[rows[-1][0] + 1]]))[0]
    return gelecek

# Fırsat analizi & Telegram bildirimi
async def firsat_analiz_ve_gonder():
    altin, usd, puan = veri_cek()
    tahmin = altin_tahmini()
    if tahmin and altin and tahmin > altin * 1.01 and puan > 0.2:
        mesaj = f"""🚨 *Fırsat Algılandı!*

Tahmini altın fiyatı: {tahmin:.2f}
Şu anki fiyat: {altin:.2f}
Haber etkisi pozitif ({puan:.2f})"""
        await bot_app.bot.send_message(chat_id=CHAT_ID, text=mesaj, parse_mode="Markdown")

# Komut: /durum
async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    if row:
        mesaj = f"📊 Son Veri\nTarih: {row[0]}\nAltın: {row[1]}\nUSD: {row[2]}\nHaber Puanı: {row[3]:.2f}"
    else:
        mesaj = "Veri bulunamadı."
    await update.message.reply_text(mesaj)

# Flask servisi
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot çalışıyor."

def flask_thread():
    web_app.run(host="0.0.0.0", port=5000)

# Telegram bot başlatıcı
async def start_bot():
    global bot_app
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("durum", durum))
    print("✅ Telegram botu başlatıldı")

    # Fırsat analiz döngüsü
    async def analiz_dongusu():
        while True:
            await firsat_analiz_ve_gonder()
            await asyncio.sleep(900)

    # Arka planda analiz döngüsünü başlat
    asyncio.create_task(analiz_dongusu())

    # Botu başlat
    await bot_app.run_polling(stop_signals=None)

# Ana giriş
if __name__ == "__main__":
    threading.Thread(target=flask_thread, daemon=True).start()

    try:
        asyncio.run(start_bot())
    except RuntimeError as e:
        if "already running" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(start_bot())
            loop.run_forever()
        else:
            raise
