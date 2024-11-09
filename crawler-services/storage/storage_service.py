import os
import json
import logging
from kafka import KafkaConsumer
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# MongoDB configuration
mongo_host = os.getenv('MONGO_HOST', 'mongo')
mongo_port = int(os.getenv('MONGO_PORT', 27017))
mongo_db_name = os.getenv('MONGO_DB_NAME', 'web_crawler')
mongo_collection_name = os.getenv('MONGO_COLLECTION_NAME', 'pages')

# Initialize MongoDB client
client = MongoClient(host=mongo_host, port=mongo_port)
db = client[mongo_db_name]
collection = db[mongo_collection_name]

# Kafka configuration
kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
parsed_pages_topic = 'parsed_pages'

# Initialize Kafka Consumer
consumer = KafkaConsumer(
    parsed_pages_topic,
    bootstrap_servers=kafka_bootstrap_servers,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='storage-service-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

def main():
    logging.info("Storage Service is starting...")
    for message in consumer:
        try:
            parsed_data = message.value
            url = parsed_data.get('url')
            logging.info(f"Storing data for URL: {url}")

            # Insert or update the parsed data into MongoDB
            collection.update_one(
                {'url': url},
                {'$set': parsed_data},
                upsert=True
            )
            logging.info(f"Data stored successfully for URL: {url}")

        except Exception as e:
            logging.error(f"Error storing data: {e}")

    consumer.close()

if __name__ == '__main__':
    main()
