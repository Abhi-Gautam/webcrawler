import scrapy
from kafka import KafkaProducer
import json
import os
import redis
from urllib.parse import urljoin, urlparse
import logging

class FetcherSpider(scrapy.Spider):
    name = "fetcher_spider"

    custom_settings = {
        'DOWNLOAD_DELAY': 1,  # Respectful crawling with a 1-second delay
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'ROBOTSTXT_OBEY': True,
        'DEPTH_LIMIT': 1,
    }

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

    # Initialize Redis client
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

    urls_to_crawl_topic = 'urls_to_crawl'
        

    def __init__(self, start_urls=None, *args, **kwargs):
        super(FetcherSpider, self).__init__(*args, **kwargs)
        start_urls_env = os.getenv('START_URLS')
        if start_urls_env:
            self.start_urls = start_urls_env.split(',')
            logging.info(f"Starting URLs from environment variable: {self.start_urls}")
        elif 'start_urls' in kwargs:
            self.start_urls = kwargs['start_urls'].split(',')
            logging.info(f"Starting URLs from command-line argument: {self.start_urls}")
        else:
            self.start_urls = ['https://google.com']  # Default URL
            logging.info(f"No starting URLs provided. Using default: {self.start_urls}")

        # Initialize Kafka Producer
        self.producer = KafkaProducer(
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def parse(self, response):
        # Prepare the data to send
        page_content = {
            'url': response.url,
            'body': response.text,
            'status': response.status,
            'headers': {k.decode('utf-8'): [i.decode('utf-8') for i in v] for k, v in response.headers.items()},
        }

        # Send data to Kafka
        self.producer.send('fetched_pages', page_content)

        # Extract and follow links
        links = set()
        for link in response.css('a::attr(href)').getall():
            normalized_url = self.normalize_url(link, page_content['url'])
            if normalized_url and not self.is_url_crawled(normalized_url):
                links.add(normalized_url)

        for link in links:
            self.producer.send(self.urls_to_crawl_topic, {'url': link})

        for link in links:
            self.mark_url_as_crawled(link)
            yield response.follow(link, self.parse)
    
    def normalize_url(self, href, base_url):
        # Resolve relative URLs
        absolute_url = urljoin(base_url, href)
        # Parse and normalize
        parsed_url = urlparse(absolute_url)
        if parsed_url.scheme not in ('http', 'https'):
            return None
        normalized_url = parsed_url._replace(fragment='').geturl()
        return normalized_url

    def is_url_crawled(self, url):
        # Check if the URL is already crawled
        return self.redis_client.sismember('crawled_urls', url)

    def mark_url_as_crawled(self, url):
        # Add the URL to the set of crawled URLs
        self.redis_client.sadd('crawled_urls', url)

    def closed(self, reason):
        # Close Kafka producer gracefully
        self.producer.flush()
        self.producer.close()
