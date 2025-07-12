import os
import base64
import time
import sqlite3
import requests
import joblib
import pandas as pd
from dotenv import load_dotenv
from textblob import TextBlob
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split

load_dotenv()

API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Google Drive API Credentials dosyasını oluştur (env'den base64)
def write_google_credentials():
    creds_base64 = os.getenv('GOOGLE_CREDS_BASE64')
    if creds_base64:
        with open('credentials.json', 'wb') as f:
            f.write(base64.b64decode(creds_base64))
        print("✅ credentials.json dosyası oluşturuldu.")
    else:
        print("❌ GOOGLE_CREDS_BASE64 env var bulunamadı!")

write_google_credentials()

# Google Drive servis objesi oluştur
def get_drive_service():
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

drive_service = get_drive_service()

def upload_file_to_drive(file_path, mime_type):
    """Dosya Drive'da varsa günceller, yoksa yeni yükler."""
    file_name = os.path.basename(file_path)
    try:
        results = drive_service.files().list(
            q=f"name='{file_name}' and trashed=false",
            spaces='drive',
            fields="files(id, name)"
        ).execute()
        files = results.get('files', [])

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        if files:
            file_id = files[0]['id']
            drive_service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            print(f"🔄 '{file_name}' Drive'da güncellendi.")
        else:
            file_metadata = {'name': file_name}
            drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print(f"✅ '{file_name}' Drive'a yüklendi.")
    except Exception as e:
        print(f"⚠️ Drive'a yükleme hatası: {e}")

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

DB_NAME = "altin_fiyatlari.db"
MODEL_FILE = "model.pkl"
THRESHOLD_STD_DEV = 0.5

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS altin (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    xautry REAL,
                    usd REAL,
                    haber TEXT,
                    duygu REAL
                )''')
    conn.commit()
    conn.close()

def fetch_data():
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote-short/XAU/USD?apikey={API_KEY}"
        xau_data = requests.get(url).json()
        if not xau_data or "price" not in xau_data[0]:
            print("❌ XAU verisi alınamadı")
            return

        xau_usd = float(xau_data[0]["price"])

        usd_try_url = f"https://financialmodelingprep.com/api/v3/quote/USD/TRY?apikey={API_KEY}"
        usd_data = requests.get(usd_try_url).json()
        usd = usd_data[0]["price"]
        if not isinstance(usd, (int, float)):
            print(f"USD verisi geçersiz: {usd_data}")
            return

        xautry = xau_usd * usd

        news_url = f"https://financialmodelingprep.com/api/v3/fmp/articles?page=0&size=1&apikey={API_KEY}"
        news_data = requests.get(news_url).json()
        latest_news = news_data[0]["content"] if news_data else ""
        sentiment = TextBlob(latest_news).sentiment.polarity

        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO altin (timestamp, xautry, usd, haber, duygu) VALUES (?, ?, ?, ?, ?)",
                  (timestamp, xautry, usd, latest_news, sentiment))
        conn.commit()
        conn.close()

        print(f"✅ Veri kaydedildi: {xautry:.2f} TL")

        detect_opportunity()
    except Exception as e:
        print(f"🚨 Veri çekme hatası: {e}")

def train_model():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM altin", conn)
    conn.close()

    if len(df) < 100:
        print("Veri seti çok küçük, model eğitilmedi.")
        return

    df = df.dropna()

    X = df[["usd", "duygu"]]
    y = df["xautry"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    model = XGBRegressor(n_estimators=100, learning_rate=0.1)
    model.fit(X_train, y_train)

    joblib.dump(model, MODEL_FILE)
    print("🧠 Model eğitildi ve kaydedildi.")

    # Drive'a yedekle
    upload_file_to_drive(MODEL_FILE, 'application/octet-stream')
    upload_file_to_drive('main.py', 'text/x-python')
    upload_file_to_drive('requirements.txt', 'text/plain')
    upload_file_to_drive('Dockerfile', 'text/plain')

def detect_opportunity():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM altin", conn)
        conn.close()

        if len(df) < 30:
            return

        df = df.dropna()
        last_row = df.iloc[-1]
        current_price = last_row["xautry"]

        model = joblib.load(MODEL_FILE)
        predicted = model.predict([[last_row["usd"], last_row["duygu"]]])[0]

        mean_price = df["xautry"].mean()
        std_dev = df["xautry"].std()

        if current_price < mean_price - THRESHOLD_STD_DEV * std_dev:
            message = (
                f"📉 *Fırsat Tespit Edildi!*\n\n"
                f"🔻 Anlık Fiyat: {current_price:.2f} TL\n"
                f"📈 Tahmini Fiyat: {predicted:.2f} TL\n"
                f"📊 Ortalama: {mean_price:.2f} TL\n"
                f"🧠 Duygu Skoru: {last_row['duygu']:.2f}"
            )
            bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            print("📤 Fırsat bildirildi.")
    except Exception as e:
        print(f"⚠️ Fırsat tespiti hatası: {e}")

@app.route('/')
def home():
    return "✅ Bot çalışıyor."

def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_data, 'interval', minutes=10)
    scheduler.start()
    print("🕒 Zamanlayıcı başlatıldı.")

if __name__ == "__main__":
    init_db()
    if not os.path.exists(MODEL_FILE):
        train_model()
    run_scheduler()
    print("✅ Telegram botu başlatıldı")
    app.run(host="0.0.0.0", port=5000)
