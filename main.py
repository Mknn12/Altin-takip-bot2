import os
import base64
import time
import sqlite3
import requests
import joblib
import pandas as pd
import logging
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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration class
class Config:
    API_KEY = os.getenv("API_KEY")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    GOOGLE_CREDS_BASE64 = os.getenv("GOOGLE_CREDS_BASE64")
    
    DB_NAME = "altin_fiyatlari.db"
    MODEL_FILE = "model.pkl"
    THRESHOLD_STD_DEV = 0.5
    FETCH_INTERVAL_MINUTES = 10
    REQUEST_TIMEOUT = 10
    
    @classmethod
    def validate(cls):
        required = ["API_KEY", "BOT_TOKEN", "CHAT_ID", "GOOGLE_CREDS_BASE64"]
        missing = [attr for attr in required if not getattr(cls, attr)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

# Validate configuration at startup
try:
    Config.validate()
    logger.info("✅ Configuration validated successfully")
except ValueError as e:
    logger.error(f"❌ Configuration error: {e}")
    exit(1)

# Google Drive API Credentials dosyasını oluştur (env'den base64)
def write_google_credentials():
    try:
        creds_base64 = Config.GOOGLE_CREDS_BASE64
        if creds_base64:
            with open('credentials.json', 'wb') as f:
                f.write(base64.b64decode(creds_base64))
            logger.info("✅ credentials.json dosyası oluşturuldu.")
        else:
            logger.error("❌ GOOGLE_CREDS_BASE64 env var bulunamadı!")
            return False
        return True
    except Exception as e:
        logger.error(f"❌ Google credentials yazma hatası: {e}")
        return False

# Google Drive servis objesi oluştur
def get_drive_service():
    try:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"❌ Google Drive servis oluşturma hatası: {e}")
        return None

def upload_file_to_drive(file_path, mime_type):
    """Dosya Drive'da varsa günceller, yoksa yeni yükler."""
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ Dosya bulunamadı: {file_path}")
        return False
        
    file_name = os.path.basename(file_path)
    try:
        drive_service = get_drive_service()
        if not drive_service:
            logger.error("❌ Google Drive servis bağlantısı başarısız")
            return False
            
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
            logger.info(f"🔄 '{file_name}' Drive'da güncellendi.")
        else:
            file_metadata = {'name': file_name}
            drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            logger.info(f"✅ '{file_name}' Drive'a yüklendi.")
        return True
    except Exception as e:
        logger.error(f"⚠️ Drive'a yükleme hatası: {e}")
        return False

# Initialize Flask app and Telegram bot
app = Flask(__name__)

def init_telegram_bot():
    try:
        bot = Bot(token=Config.BOT_TOKEN)
        # Test bot connection
        bot.get_me()
        logger.info("✅ Telegram bot bağlantısı başarılı")
        return bot
    except Exception as e:
        logger.error(f"❌ Telegram bot bağlantı hatası: {e}")
        return None

def init_db():
    try:
        conn = sqlite3.connect(Config.DB_NAME)
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
        logger.info("✅ Veritabanı başlatıldı")
    except Exception as e:
        logger.error(f"❌ Veritabanı başlatma hatası: {e}")
        raise

def fetch_data():
    try:
        # Fetch XAU/USD price
        url = f"https://financialmodelingprep.com/api/v3/quote-short/XAU/USD?apikey={Config.API_KEY}"
        response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
        response.raise_for_status()
        xau_data = response.json()
        
        if not xau_data or len(xau_data) == 0 or "price" not in xau_data[0]:
            logger.error("❌ XAU verisi geçersiz format")
            return
            
        xau_usd = float(xau_data[0]["price"])
        logger.info(f"📊 XAU/USD: {xau_usd}")

        # Fetch USD/TRY rate
        usd_try_url = f"https://financialmodelingprep.com/api/v3/quote/USD/TRY?apikey={Config.API_KEY}"
        usd_response = requests.get(usd_try_url, timeout=Config.REQUEST_TIMEOUT)
        usd_response.raise_for_status()
        usd_data = usd_response.json()
        
        if not usd_data or len(usd_data) == 0 or "price" not in usd_data[0]:
            logger.error("❌ USD/TRY verisi geçersiz format")
            return
            
        usd = float(usd_data[0]["price"])
        logger.info(f"📊 USD/TRY: {usd}")

        # Calculate XAU/TRY
        xautry = xau_usd * usd

        # Fetch news data
        try:
            news_url = f"https://financialmodelingprep.com/api/v3/fmp/articles?page=0&size=1&apikey={Config.API_KEY}"
            news_response = requests.get(news_url, timeout=Config.REQUEST_TIMEOUT)
            news_response.raise_for_status()
            news_data = news_response.json()
            
            if news_data and len(news_data) > 0 and "content" in news_data[0]:
                latest_news = news_data[0]["content"]
            else:
                latest_news = "No news available"
                logger.warning("⚠️ Haber verisi alınamadı")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Haber API hatası: {e}")
            latest_news = "News API error"

        # Calculate sentiment
        try:
            sentiment = TextBlob(latest_news).sentiment.polarity
        except Exception as e:
            logger.warning(f"⚠️ Duygu analizi hatası: {e}")
            sentiment = 0.0

        # Save to database
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(Config.DB_NAME)
        try:
            c = conn.cursor()
            c.execute("INSERT INTO altin (timestamp, xautry, usd, haber, duygu) VALUES (?, ?, ?, ?, ?)",
                      (timestamp, xautry, usd, latest_news, sentiment))
            conn.commit()
            logger.info(f"✅ Veri kaydedildi: {xautry:.2f} TL")
        finally:
            conn.close()

        # Check for trading opportunities
        detect_opportunity()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"🚨 API isteği hatası: {e}")
    except Exception as e:
        logger.error(f"🚨 Veri çekme hatası: {e}")

def train_model():
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        df = pd.read_sql_query("SELECT * FROM altin", conn)
        conn.close()

        if len(df) < 100:
            logger.warning("⚠️ Veri seti çok küçük, model eğitilmedi.")
            return False

        df = df.dropna()
        
        # Check if we still have enough data after cleaning
        if len(df) < 50:
            logger.warning("⚠️ Temizleme sonrası veri seti çok küçük")
            return False
            
        # Check for required columns
        required_columns = ["usd", "duygu", "xautry"]
        if not all(col in df.columns for col in required_columns):
            logger.error("⚠️ Gerekli sütunlar bulunamadı")
            return False

        X = df[["usd", "duygu"]]
        y = df["xautry"]

        # Check for valid data
        if X.empty or y.empty:
            logger.error("⚠️ Eğitim verisi boş")
            return False

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = XGBRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
        model.fit(X_train, y_train)

        # Save model
        joblib.dump(model, Config.MODEL_FILE)
        logger.info("🧠 Model eğitildi ve kaydedildi.")

        # Backup to Google Drive
        upload_file_to_drive(Config.MODEL_FILE, 'application/octet-stream')
        upload_file_to_drive('main.py', 'text/x-python')
        
        # Try to upload additional files if they exist
        additional_files = ['requirements.txt', 'Dockerfile', '.env.example']
        for file_path in additional_files:
            if os.path.exists(file_path):
                upload_file_to_drive(file_path, 'text/plain')
        
        return True
        
    except Exception as e:
        logger.error(f"🚨 Model eğitimi hatası: {e}")
        return False

def detect_opportunity():
    try:
        # Check if model exists
        if not os.path.exists(Config.MODEL_FILE):
            logger.warning("⚠️ Model dosyası bulunamadı, fırsat tespiti yapılamıyor.")
            return

        conn = sqlite3.connect(Config.DB_NAME)
        df = pd.read_sql_query("SELECT * FROM altin", conn)
        conn.close()

        if len(df) < 30:
            logger.info("⚠️ Yeterli veri yok, fırsat tespiti yapılamıyor.")
            return

        df = df.dropna()
        
        if df.empty:
            logger.warning("⚠️ Temizleme sonrası veri kalmadı")
            return
            
        last_row = df.iloc[-1]
        current_price = last_row["xautry"]

        # Load model and make prediction
        model = joblib.load(Config.MODEL_FILE)
        predicted = model.predict([[last_row["usd"], last_row["duygu"]]])[0]

        # Calculate statistics
        mean_price = df["xautry"].mean()
        std_dev = df["xautry"].std()

        # Check for opportunity
        if current_price < mean_price - Config.THRESHOLD_STD_DEV * std_dev:
            message = (
                f"📉 *Fırsat Tespit Edildi!*\n\n"
                f"🔻 Anlık Fiyat: {current_price:.2f} TL\n"
                f"📈 Tahmini Fiyat: {predicted:.2f} TL\n"
                f"📊 Ortalama: {mean_price:.2f} TL\n"
                f"🧠 Duygu Skoru: {last_row['duygu']:.2f}\n"
                f"📊 Standart Sapma: {std_dev:.2f}"
            )
            
            # Send Telegram notification
            bot = init_telegram_bot()
            if bot:
                try:
                    bot.send_message(chat_id=Config.CHAT_ID, text=message, parse_mode="Markdown")
                    logger.info("📤 Fırsat bildirildi.")
                except Exception as telegram_error:
                    logger.error(f"⚠️ Telegram mesaj gönderme hatası: {telegram_error}")
            else:
                logger.error("❌ Telegram bot bağlantısı kurulamadı")
                
    except Exception as e:
        logger.error(f"⚠️ Fırsat tespiti hatası: {e}")

@app.route('/')
def home():
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        df = pd.read_sql_query("SELECT COUNT(*) as count FROM altin", conn)
        conn.close()
        record_count = df.iloc[0]['count']
        
        model_status = "✅ Var" if os.path.exists(Config.MODEL_FILE) else "❌ Yok"
        
        return f"""
        <h1>🏅 Altın Fiyat Takip Botu</h1>
        <p>📊 Toplam Kayıt: {record_count}</p>
        <p>🧠 Model Durumu: {model_status}</p>
        <p>⚡ Bot Durumu: ✅ Çalışıyor</p>
        <p>🕒 Son Güncelleme: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        """
    except Exception as e:
        logger.error(f"❌ Dashboard hatası: {e}")
        return f"⚠️ Dashboard hatası: {str(e)}"

@app.route('/status')
def status():
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        df = pd.read_sql_query("SELECT * FROM altin ORDER BY timestamp DESC LIMIT 1", conn)
        conn.close()
        
        if df.empty:
            return {"status": "error", "message": "No data available"}
            
        last_record = df.iloc[0]
        return {
            "status": "success",
            "last_update": last_record['timestamp'],
            "current_price": float(last_record['xautry']),
            "usd_rate": float(last_record['usd']),
            "sentiment": float(last_record['duygu']),
            "model_exists": os.path.exists(Config.MODEL_FILE)
        }
    except Exception as e:
        logger.error(f"❌ Status endpoint hatası: {e}")
        return {"status": "error", "message": str(e)}

def main():
    logger.info("🚀 Altın Fiyat Takip Botu başlatılıyor...")
    
    # Write Google credentials
    if not write_google_credentials():
        logger.error("❌ Google credentials yazılamadı, Drive yedekleme devre dışı")
    
    # Initialize database
    init_db()
    
    # Train model if it doesn't exist
    if not os.path.exists(Config.MODEL_FILE):
        logger.info("🧠 Model bulunamadı, eğitim başlatılıyor...")
        if not train_model():
            logger.warning("⚠️ Model eğitimi başarısız, fırsat tespiti devre dışı")
    else:
        logger.info("✅ Model mevcut")
    
    # Start background scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        fetch_data, 
        'interval', 
        minutes=Config.FETCH_INTERVAL_MINUTES,
        id='fetch_data_job',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"🕒 Zamanlayıcı başlatıldı ({Config.FETCH_INTERVAL_MINUTES} dakika aralıklarla)")
    
    # Run initial data fetch
    logger.info("📊 İlk veri çekimi başlatılıyor...")
    fetch_data()
    
    try:
        logger.info("✅ Flask sunucusu başlatılıyor...")
        app.run(host="0.0.0.0", port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("🛑 Uygulama manuel olarak durduruldu")
    except Exception as e:
        logger.error(f"❌ Flask sunucusu hatası: {e}")
    finally:
        scheduler.shutdown()
        logger.info("🔌 Zamanlayıcı kapatıldı")

if __name__ == "__main__":
    main()
