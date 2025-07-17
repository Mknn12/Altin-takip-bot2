# Temel imaj olarak Python 3.10 slim kullanıyoruz
FROM python:3.10-slim

# Çalışma dizinini belirle
WORKDIR /app

# Pip'i güncelle
RUN python -m pip install --upgrade pip

# requirements.txt dosyasını konteynıra kopyala
COPY requirements.txt requirements.txt

# Gereken paketleri yükle
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını konteynıra kopyala
COPY . .

# Uygulamanın çalışacağı port (örneğin Flask için)
EXPOSE 10000

# Uygulamayı çalıştır
CMD ["python", "main.py"]
