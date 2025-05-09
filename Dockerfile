FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    chromium-driver chromium && \
    apt-get clean

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENV DISPLAY=:99

CMD ["python", "crawl.py"]