import os
import sqlite3
import json
from scrapy import Spider, Request
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timedelta
import re
import hashlib
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')

class OptimizedIncrementalGramSpider(Spider):
    name = "gram"
    allowed_domains = ['gramerkagoj.com']
    start_urls = ['https://www.gramerkagoj.com/']

    def __init__(self, *args, **kwargs):
        super(OptimizedIncrementalGramSpider, self).__init__(*args, **kwargs)
        
        db_dir = 'db'
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        db_path = os.path.join(db_dir, 'optimized_gram.db')
        self.db_connection = sqlite3.connect(db_path)
        self.db_cursor = self.db_connection.cursor()
        self._setup_database()

        self.current_crawl_date = datetime.now().date()
        self.last_crawl_date = self._get_last_crawl_date()

    def _setup_database(self):
        self.db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                url TEXT PRIMARY KEY,
                last_crawled_at DATE,
                content_hash TEXT
            )
        ''')
        self.db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawl_info (
                last_crawl_date DATE
            )
        ''')
        self.db_connection.commit()

    def _get_last_crawl_date(self):
        self.db_cursor.execute('SELECT last_crawl_date FROM crawl_info ORDER BY last_crawl_date DESC LIMIT 1')
        result = self.db_cursor.fetchone()
        return datetime.strptime(result[0], '%Y-%m-%d').date() if result else None

    def _update_last_crawl_date(self):
        self.db_cursor.execute('INSERT INTO crawl_info (last_crawl_date) VALUES (?)', (self.current_crawl_date.strftime('%Y-%m-%d'),))
        self.db_connection.commit()

    def _get_url_info(self, url):
        self.db_cursor.execute('SELECT last_crawled_at, content_hash FROM urls WHERE url = ?', (url,))
        return self.db_cursor.fetchone()

    def _update_url_info(self, url, content_hash):
        self.db_cursor.execute('''
            INSERT OR REPLACE INTO urls (url, last_crawled_at, content_hash) 
            VALUES (?, ?, ?)
        ''', (url, self.current_crawl_date.strftime('%Y-%m-%d'), content_hash))
        self.db_connection.commit()

    def normalize_url(self, url):
        parsed_url = urlparse(url)
        return urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip('/'), '', '', ''))

    def _extract_date_from_url(self, url):
        match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
        return datetime(*map(int, match.groups())).date() if match else None

    def _compute_content_hash(self, content):
        return hashlib.md5(content).hexdigest()

    def start_requests(self):
        yield Request(self.start_urls[0], self.parse, dont_filter=True)

    def parse(self, response):
        normalized_url = self.normalize_url(response.url)
        
        # Only process URLs starting with 'https://www.gramerkagoj.com'
        if not normalized_url.startswith('https://www.gramerkagoj.com'):
            return

        current_hash = self._compute_content_hash(response.body)
        url_info = self._get_url_info(normalized_url)

        if not url_info or current_hash != url_info[1]:
            self._update_url_info(normalized_url, current_hash)
            yield {'url': normalized_url, 'status': 'updated' if url_info else 'new'}

            # Extract and follow links
            for href in response.css('a::attr(href)').extract():
                full_url = response.urljoin(href)
                if full_url.startswith('https://www.gramerkagoj.com'):
                    normalized_link = self.normalize_url(full_url)
                    url_date = self._extract_date_from_url(normalized_link)
                    
                    if url_date:
                        # If URL date is after the last crawl date or within the last 7 days
                        if (not self.last_crawl_date or url_date > self.last_crawl_date) or \
                           (self.current_crawl_date - url_date).days <= 7:
                            yield Request(normalized_link, self.parse, dont_filter=True)
                    else:
                        # For URLs without dates (like category pages), always crawl
                        yield Request(normalized_link, self.parse, dont_filter=True)
        else:
            yield {'url': normalized_url, 'status': 'unchanged'}

    def closed(self, reason):
        self._update_last_crawl_date()
        self.db_cursor.execute('SELECT url FROM urls WHERE last_crawled_at = ?', (self.current_crawl_date.strftime('%Y-%m-%d'),))
        urls = [row[0] for row in self.db_cursor.fetchall()]
        output_dir = 'output'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(os.path.join(output_dir, f'links-gram-{self.current_crawl_date}.json'), 'w') as f:
            json.dump([{'url': url} for url in urls], f, indent=2)
        self.db_connection.close()

# Scrapy settings for optimized performance
custom_settings = {
    'CONCURRENT_REQUESTS': 32,
    'CONCURRENT_REQUESTS_PER_DOMAIN': 32,
    'DOWNLOAD_DELAY': 0.5,
    'REACTOR_THREADPOOL_MAXSIZE': 20,
    'LOG_LEVEL': 'INFO',
    'COOKIES_ENABLED': False,
    'RETRY_ENABLED': False,
    'DOWNLOAD_TIMEOUT': 15,
    'REDIRECT_ENABLED': False,
    'AJAXCRAWL_ENABLED': False,
}

# custom_settings = {
#     'CONCURRENT_REQUESTS': 64,
#     'CONCURRENT_REQUESTS_PER_DOMAIN': 64,
#     'DOWNLOAD_DELAY': 0.25,
#     'REACTOR_THREADPOOL_MAXSIZE': 20,
#     'LOG_LEVEL': 'INFO',
#     'COOKIES_ENABLED': False,
#     'RETRY_ENABLED': False,
#     'DOWNLOAD_TIMEOUT': 15,
#     'REDIRECT_ENABLED': False,
#     'AJAXCRAWL_ENABLED': False,
#     'AUTOTHROTTLE_ENABLED': True,
#     'AUTOTHROTTLE_START_DELAY': 1,
#     'AUTOTHROTTLE_MAX_DELAY': 3,
#     'AUTOTHROTTLE_TARGET_CONCURRENCY': 32,
#     'DNSCACHE_ENABLED': True,
# }