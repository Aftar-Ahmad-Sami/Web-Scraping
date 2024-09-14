import re
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Spider
from urllib.parse import urlparse, urlunparse
import sqlite3
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from queue import PriorityQueue

class TestSpider(Spider):
    name = "test"
    allowed_domains = ["lus.ac.bd"]
    start_urls = ["https://www.lus.ac.bd/"]

    # Define regex pattern for test URLs
    test_pattern = re.compile(r'^(https?:\/\/)?(www\.)?lus\.ac\.bd\/author\/.+?$')

    def __init__(self, *args, **kwargs):
        super(TestSpider, self).__init__(*args, **kwargs)
        
        if not os.path.exists('db'):
            os.makedirs('db')
        
        self.crawled_db = sqlite3.connect('db/crawled_urls.db')
        self.crawled_cursor = self.crawled_db.cursor()
        self.matched_db = sqlite3.connect('db/matched_urls.db')
        self.matched_cursor = self.matched_db.cursor()
        self._setup_databases()

        self.vectorizer = TfidfVectorizer()
        self.target_vector = self.vectorizer.fit_transform(["author faculty"])
        self.frontier = PriorityQueue()

    def _setup_databases(self):
        self.crawled_cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawled_urls (
                url TEXT PRIMARY KEY
            )
        ''')
        self.crawled_db.commit()

        self.matched_cursor.execute('''
            CREATE TABLE IF NOT EXISTS matched_urls (
                url TEXT PRIMARY KEY
            )
        ''')
        self.matched_db.commit()

    def _url_crawled(self, url):
        self.crawled_cursor.execute('SELECT 1 FROM crawled_urls WHERE url = ?', (url,))
        return self.crawled_cursor.fetchone() is not None

    def _add_crawled_url(self, url):
        self.crawled_cursor.execute('INSERT OR IGNORE INTO crawled_urls (url) VALUES (?)', (url,))
        self.crawled_db.commit()

    def _add_matched_url(self, url):
        self.matched_cursor.execute('INSERT OR IGNORE INTO matched_urls (url) VALUES (?)', (url,))
        self.matched_db.commit()

    def normalize_url(self, url):
        parsed_url = urlparse(url)
        normalized_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path.rstrip('/'),
            parsed_url.params,
            parsed_url.query,
            ''
        ))
        return normalized_url

    def calculate_similarity(self, url):
        url_vector = self.vectorizer.transform([url])
        similarity = cosine_similarity(self.target_vector, url_vector)[0][0]
        return -similarity  # Negative because PriorityQueue prioritizes lower values

    def start_requests(self):
        for url in self.start_urls:
            priority = self.calculate_similarity(url)
            self.frontier.put((priority, url))
        
        # Return an iterable (list) of requests
        return [self.next_request()]

    def next_request(self):
        while not self.frontier.empty():
            _, url = self.frontier.get()
            if not self._url_crawled(url):
                return scrapy.Request(url, callback=self.parse_item)
        return None  # Return None if there are no more URLs to crawl

    def parse_item(self, response):
        self.logger.info(f"Scraping page: {response.url}")
        normalized_url = self.normalize_url(response.url)
        self._add_crawled_url(normalized_url)

        if self.test_pattern.match(normalized_url):
            self._add_matched_url(normalized_url)
            yield {'url': normalized_url}

        links = LinkExtractor().extract_links(response)
        for link in links:
            normalized_link_url = self.normalize_url(link.url)
            if not self._url_crawled(normalized_link_url):
                priority = self.calculate_similarity(normalized_link_url)
                self.frontier.put((priority, normalized_link_url))

        next_request = self.next_request()
        if next_request:
            yield next_request

    def closed(self, reason):
        self.matched_cursor.execute('SELECT url FROM matched_urls')
        urls = [row[0] for row in self.matched_cursor.fetchall()]

        if not os.path.exists('output'):
            os.makedirs('output')

        with open('output/matched_links.json', 'w') as f:
            json.dump([{'url': url} for url in urls], f, indent=2)

        self.crawled_db.close()
        self.matched_db.close()