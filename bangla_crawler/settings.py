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