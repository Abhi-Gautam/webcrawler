import scrapy
from kafka import KafkaProducer
import json
import os
import logging

class FetcherSpider(scrapy.Spider):
    name = "fetcher_spider"

    custom_settings = {
        'DOWNLOAD_DELAY': 1,  # Respectful crawling with a 1-second delay
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'ROBOTSTXT_OBEY': True,
    }

    def __init__(self, start_urls=None, *args, **kwargs):
        super(FetcherSpider, self).__init__(*args, **kwargs)
        if 'start_urls' in kwargs:
            self.start_urls = kwargs['start_urls'].split(',')
        else:
            self.start_urls = ['https://google.com']

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
        links = response.css('a::attr(href)').getall()
        for link in links:
            yield response.follow(link, self.parse)

    def closed(self, reason):
        # Close Kafka producer gracefully
        self.producer.flush()
        self.producer.close()
