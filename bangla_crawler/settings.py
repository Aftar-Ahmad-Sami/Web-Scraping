# Existing settings
SPIDER_MODULES = ["bangla_crawler.spiders"]
NEWSPIDER_MODULE = "bangla_crawler.spiders"

# Increase concurrent requests to speed up crawling
CONCURRENT_REQUESTS = 32

# Reduce delay between requests
DOWNLOAD_DELAY = 0.5  # or lower if the website allows

# Disable cookies (if not needed)
COOKIES_ENABLED = False

# Disable Telnet Console (not needed for crawling)
TELNETCONSOLE_ENABLED = False

# Ensure logging level is set to avoid excessive logging (optional)
LOG_LEVEL = 'INFO'  # or 'WARNING' for less verbose logging

# Use the latest request fingerprinter implementation
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# Enable HTTP caching (optional, can speed up crawls)
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 0  # Never expire
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Adjust the maximum number of concurrent items processed by the item pipeline
CONCURRENT_ITEMS = 100

# Increase the DNS cache size to reduce DNS lookup overhead
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 10000

# Enable and configure AutoThrottle extension (optional)
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 5
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable Referer (if not needed)
REFERER_ENABLED = False

# Retry configuration
RETRY_ENABLED = True
RETRY_TIMES = 3  # Number of times to retry a failed page
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# Obey robots.txt rules (set to False only if you have permission to ignore robots.txt)
ROBOTSTXT_OBEY = True