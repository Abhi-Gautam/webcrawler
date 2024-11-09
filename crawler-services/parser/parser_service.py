import datetime
import os
import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from bs4 import BeautifulSoup


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Kafka configuration
kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
fetched_pages_topic = 'fetched_pages'
parsed_pages_topic = 'parsed_pages'


# Initialize Kafka Consumer
consumer = KafkaConsumer(
    fetched_pages_topic,
    bootstrap_servers=kafka_bootstrap_servers,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='parser-service-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

# Initialize Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=kafka_bootstrap_servers,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def main():
    logging.info("Parser Service is starting...")
    for message in consumer:
        try:
            page_content = message.value
            url = page_content.get('url')
            html = page_content.get('body')
            logging.info(f"Processing page: {url}")

            # Parse the HTML content
            soup = BeautifulSoup(html, 'lxml')

            # Extract data (example: title)
            title = soup.title.string if soup.title else ''

            # Prepare parsed data
            parsed_data = {
                'url': url,
                'title': title
                # Add other extracted data as needed
            }

            # Send parsed data to Kafka
            producer.send(parsed_pages_topic, parsed_data)
            logging.info(f"Sent parsed data for {url} to topic {parsed_pages_topic}")

        except Exception as e:
            logging.error(f"Error processing message: {e}")

    consumer.close()
    producer.flush()
    producer.close()


if __name__ == '__main__':
    main()