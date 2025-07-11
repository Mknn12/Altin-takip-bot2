# Temel Python 3.10 imajı
FROM python:3.10-slim

# Çalışma dizini oluştur ve ayarla
WORKDIR /app

# Gereksinimleri kopyala ve yükle
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

# Flask için 5000 portu aç
EXPOSE 5000

# Çalıştırma komutu (python dosya adını main.py olarak varsayıyorum)
CMD ["python", "main.py"]
