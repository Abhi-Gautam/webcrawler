FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY storage_service.py ./

ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ENV MONGO_HOST=mongo
ENV MONGO_PORT=27017
ENV MONGO_DB_NAME=web_crawler
ENV MONGO_COLLECTION_NAME=pages

CMD ["python", "storage_service.py"]
