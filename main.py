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
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
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
        required = ["API_KEY", "BOT_TOKEN", "CHAT_ID"]
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
            return True
        else:
            logger.warning("⚠️ GOOGLE_CREDS_BASE64 env var bulunamadı, Drive yedekleme devre dışı")
            return False
    except Exception as e:
        logger.error(f"❌ Google credentials yazma hatası: {e}")
        return False

# Google Drive servis objesi oluştur
def get_drive_service():
    try:
        if not os.path.exists('credentials.json'):
            logger.warning("⚠️ credentials.json bulunamadı")
            return None
            
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
            logger.warning("⚠️ Google Drive servis bağlantısı başarısız")
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

def fetch_gold_price():
    apis_to_try = [
        {
            "url": f"https://financialmodelingprep.com/api/v3/quote/XAUUSD?apikey={Config.API_KEY}",
            "parser": lambda data: data[0]["price"] if data and len(data) > 0 and "price" in data[0] else None
        },
        {
            "url": f"https://financialmodelingprep.com/api/v3/quote-short/XAUUSD?apikey={Config.API_KEY}",
            "parser": lambda data: data[0]["price"] if data and len(data) > 0 and "price" in data[0] else None
        },
        {
            "url": f"https://financialmodelingprep.com/api/v3/quote/XAUUSD?apikey={Config.API_KEY}",
            "parser": lambda data: data[0]["price"] if data and len(data) > 0 and "price" in data[0] else None
        }
    ]
    
    for i, api in enumerate(apis_to_try):
        try:
            logger.info(f"📡 XAU/USD API {i+1} deneniyor...")
            response = requests.get(api["url"], timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"📊 API {i+1} Response: {data}")
            
            price = api["parser"](data)
            if price is not None:
                price = float(price)
                logger.info(f"✅ XAU/USD başarıyla alındı: {price}")
                return price
            else:
                logger.warning(f"⚠️ API {i+1} - Geçersiz response format")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ API {i+1} Request hatası: {e}")
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"⚠️ API {i+1} Parse hatası: {e}")
        except Exception as e:
            logger.warning(f"⚠️ API {i+1} Genel hata: {e}")
    
    logger.error("❌ Tüm XAU/USD API'leri başarısız")
    return None

def fetch_usd_try_rate():
    apis_to_try = [
        f"https://financialmodelingprep.com/api/v3/quote/USDTRY?apikey={Config.API_KEY}",
        f"https://financialmodelingprep.com/api/v3/quote-short/USDTRY?apikey={Config.API_KEY}"
    ]
    
    for i, url in enumerate(apis_to_try):
        try:
            logger.info(f"📡 USD/TRY API {i+1} deneniyor...")
            response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"📊 USD/TRY API {i+1} Response: {data}")
            
            if data and len(data) > 0 and "price" in data[0]:
                usd_try = float(data[0]["price"])
                logger.info(f"✅ USD/TRY başarıyla alındı: {usd_try}")
                return usd_try
            else:
                logger.warning(f"⚠️ USD/TRY API {i+1} - Geçersiz response format")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ USD/TRY API {i+1} Request hatası: {e}")
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"⚠️ USD/TRY API {i+1} Parse hatası: {e}")
        except Exception as e:
            logger.warning(f"⚠️ USD/TRY API {i+1} Genel hata: {e}")
    
    logger.error("❌ Tüm USD/TRY API'leri başarısız")
    return None

def fetch_news_sentiment():
    try:
        news_url = f"https://financialmodelingprep.com/api/v3/fmp/articles?page=0&size=1&apikey={Config.API_KEY}"
        response = requests.get(news_url, timeout=Config.REQUEST_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"📰 News API Response: {data}")
        
        if data and len(data) > 0:
            if "content" in data[0]:
                news_content = data[0]["content"]
            elif "title" in data[0]:
                news_content = data[0]["title"]
            else:
                news_content = "No content available"
        else:
            news_content = "No news available"
            
        logger.info(f"📰 Haber içeriği alındı: {news_content[:100]}...")
        
        try:
            sentiment = TextBlob(news_content).sentiment.polarity
            logger.info(f"💭 Duygu skoru: {sentiment}")
        except Exception as e:
            logger.warning(f"⚠️ Duygu analizi hatası: {e}")
            sentiment = 0.0
            
        return news_content, sentiment
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Haber API hatası: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Haber işleme hatası: {e}")
    
    return "News API error", 0.0

def fetch_data():
    try:
        logger.info("📊 Veri çekimi başlatılıyor...")
        
        xau_usd = fetch_gold_price()
        if xau_usd is None:
            logger.error("❌ XAU/USD verisi alınamadı, veri çekimi iptal edildi")
            return
            
        usd_try = fetch_usd_try_rate()
        if usd_try is None:
            logger.error("❌ USD/TRY verisi alınamadı, veri çekimi iptal edildi")
            return
            
        xau_try = xau_usd * usd_try
        logger.info(f"💰 XAU/TRY hesaplandı: {xau_try:.2f} TL")
        
        news_content, sentiment = fetch_news_sentiment()
        
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(Config.DB_NAME)
        try:
            c = conn.cursor()
            c.execute("""
                INSERT INTO altin (timestamp, xautry, usd, haber, duygu) 
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, xau_try, usd_try, news_content, sentiment))
            conn.commit()
            logger.info(f"✅ Veri başarıyla kaydedildi: {xau_try:.2f} TL")
        finally:
            conn.close()

        detect_opportunity()
        
    except Exception as e:
        logger.error(f"🚨 Veri çekme genel hatası: {e}")

def train_model():
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        df = pd.read_sql_query("SELECT * FROM altin", conn)
        conn.close()

        logger.info(f"📊 Veritabanında {len(df)} kayıt bulundu")
        
        if len(df) < 10:
            logger.warning("⚠️ Model eğitimi için yeterli veri yok (minimum 10 kayıt)")
            return False

        df = df.dropna()
        logger.info(f"📊 Temizleme sonrası {len(df)} kayıt kaldı")
        
        if len(df) < 10:
            logger.warning("⚠️ Temizleme sonrası yeterli veri yok")
            return False
            
        required_columns = ["usd", "duygu", "xautry"]
        if not all(col in df.columns for col in required_columns):
            logger.error("⚠️ Gerekli sütunlar bulunamadı")
            return False

        X = df[["usd", "duygu"]]
        y = df["xautry"]

        if X.empty or y.empty or len(X) != len(y):
            logger.error("⚠️ Eğitim verisi geçersiz")
            return False

        test_size = min(0.2, max(0.1, 5.0 / len(df)))
        
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
        except ValueError as e:
            logger.error(f"⚠️ Train-test split hatası: {e}")
            return False

        model = XGBRegressor(
            n_estimators=min(100, len(X_train) * 2),
            learning_rate=0.1,
            max_depth=3,
            random_state=42
        )
        
        model.fit(X_train, y_train)

        joblib.dump(model, Config.MODEL_FILE)
        logger.info("🧠 Model başarıyla eğitildi ve kaydedildi")

        if os.path.exists('credentials.json'):
            upload_file_to_drive(Config.MODEL_FILE, 'application/octet-stream')
            upload_file_to_drive(Config.DB_NAME, 'application/octet-stream')
        
        return True
        
    except Exception as e:
        logger.error(f"🚨 Model eğitimi hatası: {e}")
        return False

def detect_opportunity():
    try:
        if not os.path.exists(Config.MODEL_FILE):
            logger.info("⚠️ Model dosyası bulunamadı, fırsat tespiti yapılamıyor")
            return

        conn = sqlite3.connect(Config.DB_NAME)
        df = pd.read_sql_query("SELECT * FROM altin ORDER BY timestamp DESC LIMIT 30", conn)
        conn.close()

        if len(df) < 10:
            logger.info("⚠️ Fırsat tespiti için yeterli veri yok")
            return

        df = df.dropna()
        
        if df.empty:
            logger.warning("⚠️ Temizleme sonrası veri kalmadı")
            return
            
        last_row = df.iloc[0]
        current_price = last_row["xautry"]

        try:
            model = joblib.load(Config.MODEL_FILE)
            predicted = model.predict([[last_row["usd"], last_row["duygu"]]])[0]
        except Exception as e:
            logger.error(f"⚠️ Model tahmin hatası: {e}")
            return

        mean_price = df["xautry"].mean()
        std_dev = df["xautry"].std()
        
        if std_dev == 0:
            logger.warning("⚠️ Standart sapma 0, fırsat tespiti yapılamıyor")
            return

        threshold = mean_price - Config.THRESHOLD_STD_DEV * std_dev
        
        logger.info(f"📊 Fırsat Analizi - Mevcut: {current_price:.2f}, Eşik: {threshold:.2f}, Ortalama: {mean_price:.2f}")
        
        if current_price < threshold:
            message = (
                f"📉 *Fırsat Tespit Edildi!*\n\n"
                f"🔻 Anlık Fiyat: {current_price:.2f} TL\n"
                f"📈 Tahmini Fiyat: {predicted:.2f} TL\n"
                f"📊 Ortalama: {mean_price:.2f} TL\n"
                f"🎯 Fırsat Eşiği: {threshold:.2f} TL\n"
                f"🧠 Duygu Skoru: {last_row['duygu']:.2f}\n"
                f"📊 Standart Sapma: {std_dev:.2f}\n"
                f"⏰ Zaman: {last_row['timestamp']}"
            )
            
            bot = init_telegram_bot()
            if bot:
                try:
                    bot.send_message(
                        chat_id=Config.CHAT_ID, 
                        text=message, 
                        parse_mode="Markdown"
                    )
                    logger.info("📤 Fırsat bildirildi")
                except Exception as telegram_error:
                    logger.error(f"⚠️ Telegram mesaj gönderme hatası: {telegram_error}")
            else:
                logger.error("❌ Telegram bot bağlantısı kurulamadı")
        else:
            logger.info("✅ Fırsat tespit edilmedi")
                
    except Exception as e:
        logger.error(f"⚠️ Fırsat tespiti hatası: {e}")

@app.route('/')
def home():
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        df_count = pd.read_sql_query("SELECT COUNT(*) as count FROM altin", conn)
        df_last = pd.read_sql_query("SELECT * FROM altin ORDER BY timestamp DESC LIMIT 1", conn)
        conn.close()
        
        record_count = df_count.iloc[0]['count']
        model_status = "✅ Var" if os.path.exists(Config.MODEL_FILE) else "❌ Yok"
        
        last_price = "N/A"
        last_update = "N/A"
        if not df_last.empty:
            last_price = f"{df_last.iloc[0]['xautry']:.2f} TL"
            last_update = df_last.iloc[0]['timestamp']
        
        return f"""
        <h1>🏅 Altın Fiyat Takip Botu</h1>
        <p>📊 Toplam Kayıt: {record_count}</p>
        <p>💰 Son Fiyat: {last_price}</p>
        <p>🧠 Model Durumu: {model_status}</p>
        <p>⚡ Bot Durumu: ✅ Çalışıyor</p>
        <p>🕒 Son Güncelleme: {last_update}</p>
        <p>📱 Telegram Bot: {'✅ Aktif' if init_telegram_bot() else '❌ Hata'}</p>
        <p>☁️ Drive Yedek: {'✅ Aktif' if os.path.exists('credentials.json') else '❌ Devre Dışı'}</p>
        """
    except Exception as e:
        logger.error(f"❌ Dashboard hatası: {e}")
        return f"⚠️ Dashboard hatası: {str(e)}"

