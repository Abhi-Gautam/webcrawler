FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY parser_service.py ./

ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379

CMD ["python", "parser_service.py"]
