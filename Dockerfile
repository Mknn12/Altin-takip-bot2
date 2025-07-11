# Temel imaj
FROM python:3.10-slim

# Çalışma dizini
WORKDIR /app

# Gereksinimler kopyalanır
COPY requirements.txt .

# Paketler yüklenir
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyaları kopyalanır
COPY . .

# Ortam değişkenleri opsiyonel (bunları dışardan vermen iyi)
# ENV BOT_TOKEN=...
# ENV CHAT_ID=...

# Uygulama başlatılır (Flask ve asyncio ile birlikte)
CMD ["python", "main.py"]
