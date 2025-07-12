import os
import base64
import sqlite3
import requests
import joblib
import pandas as pd
from dotenv import load_dotenv
from textblob import TextBlob
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split

# Google Drive için
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

load_dotenv()

API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MODEL_FILE = "model.pkl"
DB_NAME = "altin_fiyatlari.db"
THRESHOLD_STD_DEV = 0.5  # Ortalama altı eşik çarpanı

# Google Drive klasör ID'si (model dosyasını koyacağımız klasör)
# Boş bırakırsan root'a koyar, tavsiye Drive'da kendin bir klasör açıp ID'sini buraya koy
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID") or None

# Google Drive API Ayarları
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'credentials.json'  # Bu dosyayı base64 ile .env'den diske yazıyoruz

def write_google_credentials():
    creds_base64 = os.getenv('GOOGLE_CREDS_BASE64')
    if creds_base64:
        with open(SERVICE_ACCOUNT_FILE, 'wb') as f:
            f.write(base64.b64decode(creds_base64))
    else:
        print("GOOGLE_CREDS_BASE64 env var bulunamadı!")

write_google_credentials()

# Google Drive Servisi oluşturma
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=credentials)
    return service

# Drive'a dosya yükleme veya güncelleme
def upload_file_to_drive(filename, mimetype='application/octet-stream'):
    service = get_drive_service()

    # Önce aynı ada sahip dosya var mı diye arıyoruz
    query = f"name='{filename}'"
    if GOOGLE_DRIVE_FOLDER_ID:
        query += f" and '{GOOGLE_DRIVE_FOLDER_ID}' in parents"
    results = service.files().list(q=query, spaces='drive',
                                   fields="files(id, name)").execute()
    files = results.get('files', [])

    media = MediaFileUpload(filename, mimetype=mimetype, resumable=True)

    if files:
        # Dosya varsa güncelle
        file_id = files[0]['id']
        updated_file = service.files().update(fileId=file_id,
                                              media_body=media).execute()
        print(f"Google Drive: '{filename}' güncellendi.")
    else:
        # Yoksa yeni dosya oluştur
        file_metadata = {'name': filename}
        if GOOGLE_DRIVE_FOLDER_ID:
            file_metadata['parents'] = [GOOGLE_DRIVE_FOLDER_ID]
        file = service.files().create(body=file_metadata,
                                      media_body=media,
                                      fields='id').execute()
        print(f"Google Drive: '{filename}' yüklendi.")

# Drive'dan dosya indirme
def download_file_from_drive(filename):
    service = get_drive_service()

    query = f"name='{filename}'"
    if GOOGLE_DRIVE_FOLDER_ID:
        query += f" and '{GOOGLE_DRIVE_FOLDER_ID}' in parents"
    results = service.files().list(q=query, spaces='drive',
                                   fields="files(id, name)").execute()
    files = results.get('files', [])

    if not files:
        print(f"Google Drive: '{filename}' bulunamadı.")
        return False

    file_id = files[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(filename, 'wb')

    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    print(f"Google Drive: '{filename}' indirildi.")
    return True

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS altin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        if not usd_data or "price" not in usd_data[0]:
            print("❌ USD verisi alınamadı")
            return

        usd = float(usd_data[0]["price"])
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

    # Model Drive'a yedekleniyor
    upload_file_to_drive(MODEL_FILE)

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

        if not os.path.exists(MODEL_FILE):
            print("Model dosyası bulunamadı, fırsat tespiti yapılamıyor.")
            return

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

    # Model varsa Drive'dan indir ve yükle, yoksa eğit
    if not os.path.exists(MODEL_FILE):
        print("Model dosyası yok, Drive'dan indiriliyor...")
        indirildi = download_file_from_drive(MODEL_FILE)
        if not indirildi:
            print("Drive'dan indirilemedi, model eğitilecek...")
            train_model()
    else:
        print("Model dosyası mevcut.")

    run_scheduler()
    print("✅ Telegram botu başlatıldı")
    app.run(host="0.0.0.0", port=5000)
