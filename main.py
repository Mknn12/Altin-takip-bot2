import os
import time
import requests
import sqlite3
import numpy as np
import pandas as pd
from flask import Flask, request
from threading import Thread
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler
from textblob import TextBlob
import datetime
import logging

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

KEYWORDS = ["faiz", "cumhurbaşkanı", "merkez bankası", "enflasyon"]

DB_PATH = "veri.db"
MODEL_PATH = "lstm_model.h5"
SCALER_PATH = "scaler.npy"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS altin (
        zaman TEXT,
        fiyat REAL
    )""")
    conn.commit()
    conn.close()

def get_gold_price():
    try:
        url = "https://api.exchangerate.host/latest?base=XAU&symbols=TRY"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data["rates"]["TRY"]
    except Exception as e:
        logging.error(f"Altın fiyatı çekme hatası: {e}")
        return None

def get_finance_news():
    news_sources = [
        ("https://newsdata.io/api/1/news?apikey=demo&q=finance&country=tr", "results"),
        # İstersen burada ücretsiz başka haber API'ları ekleyebilirsin.
    ]
    titles = []
    for url, key in news_sources:
        try:
            response = requests.get(url, timeout=10)
            articles = response.json().get(key, [])
            titles.extend([a["title"] for a in articles])
        except Exception as e:
            logging.error(f"Haber çekme hatası ({url}): {e}")
    return titles[:10]

def analyze_news(news_titles):
    results = []
    for title in news_titles:
        sentiment = TextBlob(title).sentiment.polarity
        keywords_found = [kw for kw in KEYWORDS if kw in title.lower()]
        results.append((title, sentiment, keywords_found))
    return results

def save_price(fiyat):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    zaman = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO altin (zaman, fiyat) VALUES (?, ?)", (zaman, fiyat))
    conn.commit()
    conn.close()

def load_prices():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM altin", conn)
    conn.close()
    return df

def train_model():
    df = load_prices()
    if len(df) < 30:
        logging.info("Yeterli veri yok, model eğitilemiyor.")
        return False
    data = df.copy()
    scaler = MinMaxScaler()
    data["fiyat_scaled"] = scaler.fit_transform(data["fiyat"].values.reshape(-1,1))

    seq_len = 10
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data["fiyat_scaled"].values[i:i+seq_len])
        y.append(data["fiyat_scaled"].values[i+seq_len])
    X, y = np.array(X), np.array(y)
    X = X.reshape((X.shape[0], X.shape[1], 1))

    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(seq_len,1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(optimizer="adam", loss="mean_squared_error")
    model.fit(X, y, epochs=10, batch_size=8, verbose=0)

    model.save(MODEL_PATH)
    np.save(SCALER_PATH, scaler.scale_)
    np.save(SCALER_PATH.replace(".npy", "_min.npy"), scaler.min_)
    logging.info("Model eğitildi ve kaydedildi.")
    return True

def load_model_and_scaler():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
        return None, None
    from tensorflow.keras.models import load_model
    model = load_model(MODEL_PATH)
    scale_ = np.load(SCALER_PATH)
    min_ = np.load(SCALER_PATH.replace(".npy", "_min.npy"))
    scaler = MinMaxScaler()
    scaler.scale_ = scale_
    scaler.min_ = min_
    scaler.data_min_ = 0
    scaler.data_max_ = 1
    scaler.data_range_ = 1
    return model, scaler

def lstm_predict(prices):
    model, scaler = load_model_and_scaler()
    if model is None or scaler is None or len(prices) < 10:
        return None
    scaled = scaler.transform(prices["fiyat"].values.reshape(-1,1))
    seq_len = 10
    X = []
    X.append(scaled[-seq_len:].reshape(seq_len, 1))
    X = np.array(X)
    pred_scaled = model.predict(X)[0][0]
    # Tahmini geri ölçeğe dönüştür
    pred = pred_scaled * (1 / scaler.scale_[0]) - scaler.min_[0] / scaler.scale_[0]
    return pred

def calc_confidence_score():
    # Basit güven skoru: son 10 tahminin ortalama hata yüzdesi baz alınır
    df = load_prices()
    if len(df) < 20:
        return None
    model, scaler = load_model_and_scaler()
    if model is None or scaler is None:
        return None
    errors = []
    seq_len = 10
    data = df.copy()
    scaled = scaler.transform(data["fiyat"].values.reshape(-1,1))
    for i in range(len(data)-seq_len-1):
        X = scaled[i:i+seq_len].reshape(1, seq_len, 1)
        pred = model.predict(X)[0][0]
        true = scaled[i+seq_len][0]
        errors.append(abs(true - pred))
    if not errors:
        return None
    avg_error = np.mean(errors)
    confidence = max(0, 100 - avg_error*1000)  # kabaca yüzdelik bir skor
    return round(confidence, 2)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logging.error(f"Telegram mesajı gönderme hatası: {e}")

def monitor_loop():
    last_train_date = None
    while True:
        fiyat = get_gold_price()
        if fiyat:
            save_price(fiyat)
            now_date = datetime.date.today()
            if last_train_date != now_date:
                train_model()
                last_train_date = now_date

            df = load_prices()
            tahmin = lstm_predict(df.tail(50))
            haberler = get_finance_news()
            analiz = analyze_news(haberler)
            confidence = calc_confidence_score()

            mesaj = ""
            for title, sentiment, keywords in analiz:
                if keywords or sentiment < -0.1:
                    mesaj += f"📢 Haber: {title}\n➡ Duygu: {'Negatif' if sentiment < 0 else 'Pozitif'}\nAnahtar: {', '.join(keywords)}\n\n"

            if tahmin and fiyat < tahmin * 0.97:
                mesaj += f"💰 Fırsat: Altın şu anda {fiyat:.2f} ₺, tahmin {tahmin:.2f} ₺\n"
                if confidence is not None:
                    mesaj += f"🔒 Güven skoru: %{confidence}\n"

            if mesaj:
                send_telegram_message(mesaj)

        time.sleep(600)  # 10 dakikada bir kontrol

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if "message" in data:
        text = data["message"].get("text", "")
        if text == "/durum":
            fiyat = get_gold_price()
            send_telegram_message(f"📊 Gram altın: {fiyat:.2f} ₺" if fiyat else "Fiyat alınamadı.")
    return {"ok": True}

if __name__ == "__main__":
    init_db()
    Thread(target=monitor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
