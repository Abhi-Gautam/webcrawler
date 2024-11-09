import scrapy
import os
import logging
import json
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
from queue import Queue

class FetcherSpider(scrapy.Spider):
    name = "fetcher_spider"

    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'ROBOTSTXT_OBEY': True,
    }

    def __init__(self, *args, **kwargs):
        super(FetcherSpider, self).__init__(*args, **kwargs)

        # Initialize logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

        # Initialize Kafka Producer for sending fetched pages
        kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logging.info(f"Kafka Producer initialized with bootstrap servers: {kafka_bootstrap_servers}")

        # Initialize Kafka Consumer for receiving URLs to crawl
        self.url_consumer = KafkaConsumer(
            'urls_to_crawl',
            bootstrap_servers=kafka_bootstrap_servers,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='fetcher-service-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        logging.info("Kafka Consumer for URLs initialized.")

        # Initialize a Queue to store URLs to be crawled
        self.url_queue = Queue()

        # Start a thread to consume URLs from Kafka
        Thread(target=self.consume_urls, daemon=True).start()

        # Seed URLs (if any) can be added to the queue
        start_urls_env = os.getenv('START_URLS')
        if start_urls_env:
            start_urls = start_urls_env.split(',')
            for url in start_urls:
                self.url_queue.put(url)
            logging.info(f"Added seed URLs to queue: {start_urls}")
        elif 'start_urls' in kwargs:
            start_urls = kwargs['start_urls'].split(',')
            for url in start_urls:
                self.url_queue.put(url)
            logging.info(f"Added seed URLs to queue from arguments: {start_urls}")
        else:
            default_url = 'https://google.com'
            self.url_queue.put(default_url)
            logging.info(f"No seed URLs provided. Added default URL to queue: {default_url}")

    def consume_urls(self):
        logging.info("Starting URL consumer thread.")
        for message in self.url_consumer:
            url = message.value.get('url')
            if url:
                self.url_queue.put(url)
                logging.info(f"Received new URL to crawl: {url}")

    def start_requests(self):
        while True:
            url = self.url_queue.get()
            if url:
                logging.info(f"Starting request for URL: {url}")
                yield scrapy.Request(url=url, callback=self.parse)
            self.url_queue.task_done()

    def parse(self, response):
        logging.info(f"Fetched URL: {response.url}")
        # Prepare the data to send
        page_content = {
            'url': response.url,
            'body': response.text,
            'status': response.status,
            'headers': {k.decode('utf-8'): [v.decode('utf-8') for v in vals] for k, vals in response.headers.items()},
        }

        # Send data to Kafka
        self.producer.send('fetched_pages', page_content)
        logging.info(f"Sent fetched page to Kafka: {response.url}")

        # Since we're not following links here, the crawling is controlled by the URLs provided to the queue

    def closed(self, reason):
        # Close Kafka connections
        logging.info("Closing Kafka connections.")
        self.producer.flush()
        self.producer.close()
        self.url_consumer.close()
