import os
import requests
import pandas as pd
import pickle
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.linear_model import LinearRegression
from dotenv import load_dotenv
from datetime import datetime
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import logging

load_dotenv()

app = Flask(__name__)
scheduler = BackgroundScheduler()
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

FMP_API_KEY = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_FILE = "data.csv"
MODEL_FILE = "model.pkl"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def fetch_data():
    logging.info("📊 Veri çekimi başlatılıyor...")
    for endpoint in [
        f"https://financialmodelingprep.com/api/v3/quote/XAUUSD?apikey={FMP_API_KEY}",
        f"https://financialmodelingprep.com/api/v3/quote-short/XAUUSD?apikey={FMP_API_KEY}"
    ]:
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            price = response.json()[0]["price"]
            save_data(price)
            return
        except Exception as e:
            logging.warning(f"⚠️ API Request hatası: {e}")
    logging.error("❌ XAU/USD verisi alınamadı, veri çekimi iptal edildi")

def save_data(price):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = pd.DataFrame([[now, price]], columns=["timestamp", "price"])
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df = pd.concat([df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(DATA_FILE, index=False)
    logging.info("✅ Veri dosyaya kaydedildi")
    if len(df) >= 10:
        train_model(df)

def train_model(df):
    logging.info("🤖 Model eğitimi başlatılıyor...")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["timestamp_ordinal"] = df["timestamp"].map(datetime.toordinal)
    X = df["timestamp_ordinal"].values.reshape(-1, 1)
    y = df["price"].values
    model = LinearRegression().fit(X, y)
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model, f)
    logging.info("✅ Model eğitimi tamamlandı")
    upload_to_drive(MODEL_FILE)
    send_prediction(df, model)

def send_prediction(df, model):
    future_time = datetime.now().toordinal() + 1
    predicted_price = model.predict([[future_time]])[0]
    current_price = df.iloc[-1]["price"]
    diff = predicted_price - current_price
    message = (
        f"📈 Tahmin: {predicted_price:.2f} USD\n"
        f"💰 Şu anki fiyat: {current_price:.2f} USD\n"
        f"{'📉 DÜŞÜŞ' if diff < 0 else '📈 YÜKSELİŞ'} bekleniyor!"
    )
    send_telegram(message)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload)
        logging.info("📤 Telegram mesajı gönderildi")
    except Exception as e:
        logging.error(f"Telegram hatası: {e}")

def upload_to_drive(filename):
    f = drive.CreateFile({"title": filename})
    f.SetContentFile(filename)
    f.Upload()
    logging.info(f"☁️ {filename} GDrive'a yüklendi")

@app.route("/")
def home():
    return "Bot Aktif"

scheduler.add_job(fetch_data, "interval", minutes=10)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
