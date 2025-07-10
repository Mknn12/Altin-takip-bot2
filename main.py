import os
import time
import requests
import sqlite3
import numpy as np
import pandas as pd
from flask import Flask, request
from threading import Thread
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("veri.db")
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
        response = requests.get(url)
        data = response.json()
        return data["rates"]["TRY"]
    except:
        return None

def save_price(fiyat):
    conn = sqlite3.connect("veri.db")
    c = conn.cursor()
    zaman = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO altin (zaman, fiyat) VALUES (?, ?)", (zaman, fiyat))
    conn.commit()
    conn.close()

def load_prices():
    conn = sqlite3.connect("veri.db")
    df = pd.read_sql_query("SELECT * FROM altin", conn)
    conn.close()
    return df

def lstm_predict(data):
    if len(data) < 30:
        return None

    df = data.copy()
    df["fiyat"] = MinMaxScaler().fit_transform(df["fiyat"].values.reshape(-1, 1))

    sequence_length = 10
    X, y = [], []
    for i in range(len(df) - sequence_length):
        X.append(df["fiyat"].values[i:i + sequence_length])
        y.append(df["fiyat"].values[i + sequence_length])
    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    model = Sequential()
    model.add(LSTM(units=50, return_sequences=True, input_shape=(X.shape[1], 1)))
    model.add(LSTM(units=50))
    model.add(Dense(1))
    model.compile(optimizer="adam", loss="mean_squared_error")
    model.fit(X, y, epochs=5, batch_size=8, verbose=0)

    last_sequence = df["fiyat"].values[-sequence_length:]
    last_sequence = last_sequence.reshape((1, sequence_length, 1))
    pred_scaled = model.predict(last_sequence)[0][0]

    scaler = MinMaxScaler()
    scaler.fit(data["fiyat"].values.reshape(-1, 1))
    prediction = scaler.inverse_transform([[pred_scaled]])[0][0]
    return prediction

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram hatası:", e)

def monitor():
    while True:
        fiyat = get_gold_price()
        if fiyat:
            save_price(fiyat)
            df = load_prices()
            tahmin = lstm_predict(df.tail(50))
            if tahmin and fiyat < tahmin * 0.97:
                send_telegram_message(f"📉 DÜŞÜK FİYAT: Şu an {fiyat:.2f}₺, tahmin {tahmin:.2f}₺")
        time.sleep(3600)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if "message" in data:
        text = data["message"].get("text", "")
        if text == "/durum":
            fiyat = get_gold_price()
            if fiyat:
                send_telegram_message(f"🟡 Gram altın şu anda {fiyat:.2f} ₺")
            else:
                send_telegram_message("Altın fiyatı alınamadı.")
    return {"ok": True}

if __name__ == "__main__":
    init_db()
    Thread(target=monitor, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)