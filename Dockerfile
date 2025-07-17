# Temel imaj olarak Python 3.10 slim kullanıyoruz
FROM python:3.10-slim

# Çalışma dizini oluştur ve ayarla
WORKDIR /app

# pip'i güncelle
RUN pip install --upgrade pip

# requirements.txt dosyasını kopyala
COPY requirements.txt requirements.txt

# Bağımlılıkları yükle
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Uygulamayı çalıştır
CMD ["python", "main.py"]
