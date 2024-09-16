import os
import sqlite3
import json
import csv
from scrapy import Spider, Request
from scrapy.exceptions import CloseSpider
from urllib.parse import urljoin
from datetime import datetime
import time
from twisted.internet import reactor
from scrapy.utils.reactor import install_reactor
import logging
from collections import deque

install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')

class NewsFocusedGramSpider(Spider):
    name = "cc"
    allowed_domains = ['gramerkagoj.com']
    start_urls = ['https://www.gramerkagoj.com/']

    def __init__(self, *args, **kwargs):
        super(NewsFocusedGramSpider, self).__init__(*args, **kwargs)
        
        db_dir = 'db'
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        db_path = os.path.join(db_dir, 'gram_news01.db')
        self.db_connection = sqlite3.connect(db_path)
        self.db_cursor = self.db_connection.cursor()
        self._setup_database()

        self.current_crawl_date = datetime.now()

        # Set up JSON file for URLs
        self.json_file = 'crawled_urls01.json'
        self.crawled_urls = self._load_crawled_urls()

        # New URLs discovered in this run
        self.new_urls = set()

        # Set up CSV file for saving responses
        self.csv_file = 'crawled_data.csv'
        self._setup_csv_file()

        # Time limit setup 
        self.start_time = time.time()
        self.time_limit = 120  # 2 minutes in seconds

        # Schedule spider close after time limit
        reactor.callLater(self.time_limit, self.close_spider)

        # Set up logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # BFS queue
        self.queue = deque(self.start_urls)

    def _setup_database(self):
        self.db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_articles (
                url TEXT PRIMARY KEY,
                timestamp TIMESTAMP
            )
        ''')
        self.db_connection.commit()

    def _setup_csv_file(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['url', 'timestamp'])

    def _load_crawled_urls(self):
        crawled_urls = set()
        if os.path.exists(self.json_file):
            with open(self.json_file, 'r', encoding='utf-8') as f:
                try:
                    crawled_urls = set(json.load(f))
                except json.JSONDecodeError:
                    crawled_urls = set()
        return crawled_urls

    def _save_crawled_urls(self):
        all_urls = self.crawled_urls.union(self.new_urls)
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(list(all_urls), f, ensure_ascii=False, indent=2)

    def _update_news_info(self, url):
        if url not in self.crawled_urls and url not in self.new_urls:
            current_time = datetime.now().isoformat()
            self.db_cursor.execute('''
                INSERT OR REPLACE INTO news_articles (url, timestamp) 
                VALUES (?, ?)
            ''', (url, current_time))
            self.db_connection.commit()

            # Add URL to new_urls set
            self.new_urls.add(url)

            # Save to CSV file
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([url, current_time])

            logging.info(f"New URL processed: {url}")
            return True
        else:
            logging.info(f"Skipping already crawled URL: {url}")
            return False

    def start_requests(self):
        while self.queue:
            url = self.queue.popleft()
            yield Request(url, self.parse, dont_filter=True)

    def parse(self, response):
        logging.info(f"Parsing URL: {response.url}")

        if time.time() - self.start_time > self.time_limit:
            raise CloseSpider('Time limit reached')

        new_urls_found = False

        # Extract news article links
        for article in response.css('a[href^="details.php?id="]'):
            url = urljoin(response.url, article.attrib['href'])
            
            # Process URL if it's new
            if self._update_news_info(url):
                new_urls_found = True

        # Follow pagination links
        for next_page in response.css('a.page-link::attr(href)').extract():
            if next_page is not None:
                full_url = urljoin(response.url, next_page)
                if full_url not in self.crawled_urls and full_url not in self.new_urls:
                    self.queue.append(full_url)

        logging.info(f"Finished parsing {response.url}")

    def close_spider(self):
        self.crawler.engine.close_spider(self, 'Time limit reached')

    def closed(self, reason):
        self.db_connection.close()
        self._save_crawled_urls()
        logging.info(f"Spider closed. Reason: {reason}")
        logging.info(f"Total new URLs discovered: {len(self.new_urls)}")

    custom_settings = {
        'CONCURRENT_REQUESTS': 32,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 32,
        'DOWNLOAD_DELAY': .5,
        'REACTOR_THREADPOOL_MAXSIZE': 20,
        'LOG_LEVEL': 'INFO',
        'COOKIES_ENABLED': False,
        'RETRY_ENABLED': False,
        'DOWNLOAD_TIMEOUT': 15,
        'REDIRECT_ENABLED': False,
        'AJAXCRAWL_ENABLED': False,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 3,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 8,
        'DNSCACHE_ENABLED': False,
        'HTTPCACHE_ENABLED': False,  # Disable HTTP cache
    }