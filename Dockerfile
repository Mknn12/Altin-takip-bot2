FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV API_KEY=$API_KEY
ENV BOT_TOKEN=$BOT_TOKEN
ENV CHAT_ID=$CHAT_ID
ENV GOOGLE_CREDS_BASE64=$GOOGLE_CREDS_BASE64

CMD ["python", "main.py"]
