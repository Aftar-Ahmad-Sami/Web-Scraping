
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urlparse, urlunparse
import sqlite3
import json


class BanglakagojSpider(CrawlSpider):
    name = "banglakagoj"
    allowed_domains = ["banglakagoj.com"]
    start_urls = ["https://www.banglakagoj.com/"]

    rules = (
        Rule(LinkExtractor(allow=()), callback='parse_item', follow=True),
    )

    def __init__(self, *args, **kwargs):
        super(BanglakagojSpider, self).__init__(*args, **kwargs)
        self.db_connection = sqlite3.connect('db/seen_urls-banglakagoj.db')
        self.db_cursor = self.db_connection.cursor()
        self._setup_database()

    def _setup_database(self):
        """Set up the database table if it doesn't exist."""
        self.db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                url TEXT PRIMARY KEY
            )
        ''')
        self.db_connection.commit()

    def _url_seen(self, url):
        """Check if the URL has already been seen."""
        self.db_cursor.execute('SELECT 1 FROM urls WHERE url = ?', (url,))
        return self.db_cursor.fetchone() is not None

    def _add_url(self, url):
        """Add a URL to the database."""
        self.db_cursor.execute('INSERT INTO urls (url) VALUES (?)', (url,))
        self.db_connection.commit()

    def normalize_url(self, url):
        """Normalize URL by removing fragments and trailing slashes."""
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

    def parse_item(self, response):
        self.logger.info(f"Scraping page: {response.url}")
        links = LinkExtractor().extract_links(response)
        for link in links:
            normalized_url = self.normalize_url(link.url)
            if not self._url_seen(normalized_url):
                self._add_url(normalized_url)  # Add the URL to the database
                yield {'url': normalized_url}

    def close(self, reason):
        """Save the URLs from the database to a JSON file."""
        self.db_cursor.execute('SELECT url FROM urls')
        urls = [row[0] for row in self.db_cursor.fetchall()]

        with open('output/links-banglakagoj.json', 'w') as f:
            json.dump([{'url': url} for url in urls], f, indent=2)

        self.db_connection.close()  # Close the database connection when spider is closed
