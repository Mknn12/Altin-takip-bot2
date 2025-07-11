import os
import sqlite3
import logging
import threading
import asyncio
import aiohttp
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from textblob import TextBlob
import xgboost as xgb
import numpy as np

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))  # chat id integer olmalı

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env dosyasında tanımlı değil!")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID .env dosyasında tanımlı değil!")

# Database bağlantısı
conn = sqlite3.connect("veri.db", check_same_thread=False)
c = conn.cursor()

# Tablo varsa oluştur (fiyatlar ve haberler için)
c.execute("""
CREATE TABLE IF NOT EXISTS fiyatlar (
    tarih TEXT PRIMARY KEY,
    altin REAL,
    usd REAL,
    haber_puani REAL,
    tahmin REAL
)
""")
conn.commit()
async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT * FROM fiyatlar ORDER BY tarih DESC LIMIT 1")
    row = c.fetchone()
    if row:
        mesaj = (f"📊 Son Veri\n"
                 f"Tarih: {row[0]}\n"
                 f"Altın: {row[1]}\n"
                 f"USD: {row[2]}\n"
                 f"Haber Puanı: {row[3]:.2f}\n"
                 f"Tahmin: {row[4]:.4f}")
    else:
        mesaj = "Veri bulunamadı."
    await update.message.reply_text(mesaj)
API_KEY = os.getenv("API_KEY")  # Financial Modeling Prep API Key
ALTIN_URL = f"https://financialmodelingprep.com/api/v3/metal-price/gold?apikey={API_KEY}"
USD_URL = f"https://financialmodelingprep.com/api/v3/forex?apikey={API_KEY}"
HABER_API_URL = "https://example-news-api.com/latest"  # Kendi haber API'n varsa buraya koy

async def fetch_json(session, url):
    async with session.get(url) as response:
        return await response.json()

async def getir_veriler():
    async with aiohttp.ClientSession() as session:
        altin_veri = await fetch_json(session, ALTIN_URL)
        usd_veri = await fetch_json(session, USD_URL)
        # Haberleri kendi API'nden çek
        haber_veri = await fetch_json(session, HABER_API_URL)

        # Örnek: altın fiyatı ve usd fiyatı parsing
        altin_fiyat = altin_veri['price'] if 'price' in altin_veri else None
        usd_fiyat = usd_veri[0]['bid'] if usd_veri else None

        # Haberlerden metin çek (örnek)
        haber_metinleri = " ".join([haber["title"] + " " + haber["description"] for haber in haber_veri.get("articles", [])])

        return altin_fiyat, usd_fiyat, haber_metinleri
def analiz_et(haber_metin):
    if not haber_metin:
        return 0.0
    blob = TextBlob(haber_metin)
    return blob.sentiment.polarity  # -1 ile +1 arasında değer döner
def model_egit():
    c.execute("SELECT altin, usd, haber_puani, tahmin FROM fiyatlar ORDER BY tarih")
    rows = c.fetchall()
    if len(rows) < 10:
        print("Yeterli veri yok, eğitim yapılamıyor.")
        return None

    data = np.array(rows)
    X = data[:-1, :-1].astype(float)  # altin, usd, haber_puani
    y = data[1:, 0].astype(float)     # ertesi gün altın fiyatı (kaydırılmış)

    model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=50)
    model.fit(X, y)
    return model

def model_tahmin(model, altin, usd, haber_puani):
    if not model:
        return 0.0
    X_pred = np.array([[altin, usd, haber_puani]])
    pred = model.predict(X_pred)
    return float(pred[0])
async def kaydet_ve_bildir(altin, usd, haber_puani, tahmin, app):
    tarih = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO fiyatlar (tarih, altin, usd, haber_puani, tahmin) VALUES (?, ?, ?, ?, ?)",
              (tarih, altin, usd, haber_puani, tahmin))
    conn.commit()

    # Basit fırsat tespiti: altın fiyatı tahminden %1 den fazla düşükse bildir
    if altin < tahmin * 0.99:
        mesaj = f"🚨 Fırsat! Altın fiyatı tahminin altında.\nGerçek: {altin}\nTahmin: {tahmin:.2f}"
        await app.bot.send_message(chat_id=CHAT_ID, text=mesaj)
async def periyodik_islem(app):
    while True:
        try:
            altin, usd, haber_metin = await getir_veriler()
            haber_puani = analiz_et(haber_metin)

            model = model_egit()
            tahmin = model_tahmin(model, altin, usd, haber_puani)

            await kaydet_ve_bildir(altin, usd, haber_puani, tahmin, app)

        except Exception as e:
            print(f"Hata: {e}")

        await asyncio.sleep(60*60)  # Her saat çalıştır
async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", durum))
    print("✅ Telegram botu başlatıldı")

    # Periyodik görev task olarak ekle
    asyncio.create_task(periyodik_islem(app))

    await app.run_polling()

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot çalışıyor."

def run_flask():
    web_app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(start_bot())
