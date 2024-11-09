import os
import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from bs4 import BeautifulSoup
import redis
from urllib.parse import urljoin, urlparse


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Initialize Redis client
redis_host = os.getenv('REDIS_HOST', 'redis')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

# Kafka configuration
kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
fetched_pages_topic = 'fetched_pages'
parsed_pages_topic = 'parsed_pages'
urls_to_crawl_topic = 'urls_to_crawl'

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

            # Extract links
            links = set()
            for link in soup.find_all('a', href=True):
                href = link['href']
                normalized_url = normalize_url(href, url)
                if normalized_url and not is_url_crawled(normalized_url):
                    links.add(normalized_url)

            logging.info(f"Found {len(links)} new links on {url}")

            # Mark the URL as crawled
            mark_url_as_crawled(url)

            # Prepare parsed data
            parsed_data = {
                'url': url,
                'title': title,
                # Add other extracted data as needed
            }

            # Send parsed data to Kafka
            producer.send(parsed_pages_topic, parsed_data)
            logging.info(f"Sent parsed data for {url} to topic {parsed_pages_topic}")

            # Send new URLs to Kafka
            for link in links:
                producer.send(urls_to_crawl_topic, {'url': link})
            logging.info(f"Sent {len(links)} new URLs to topic {urls_to_crawl_topic}")

        except Exception as e:
            logging.error(f"Error processing message: {e}")

    consumer.close()
    producer.flush()
    producer.close()


def normalize_url(href, base_url):
    # Resolve relative URLs
    absolute_url = urljoin(base_url, href)
    # Parse and normalize
    parsed_url = urlparse(absolute_url)
    if parsed_url.scheme not in ('http', 'https'):
        return None
    normalized_url = parsed_url._replace(fragment='').geturl()
    return normalized_url

def is_url_crawled(url):
    # Check if the URL is already crawled
    return redis_client.sismember('crawled_urls', url)

def mark_url_as_crawled(url):
    # Add the URL to the set of crawled URLs
    redis_client.sadd('crawled_urls', url)

if __name__ == '__main__':
    main()