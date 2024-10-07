import time
import sqlite3
import logging
import os
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===========================
# Configuration Parameters
# ===========================

# List of category and subcategory URLs to scrape
BASE_URLS = [
    "https://sharebiz.net/category/national-news",
    "https://sharebiz.net/category/daily-paper/first-page/",
    "https://sharebiz.net/category/international-news",
    "https://sharebiz.net/category/sports-news",
    # Add more categories and subcategories as needed
]

# Number of pages to scrape per run per category
MAX_PAGES_PER_CATEGORY = 10  # Adjust as needed

# Number of concurrent threads per batch
MAX_THREADS = 3  # Run 3 pages concurrently per batch

# Batch size for grouping page scraping tasks
BATCH_SIZE = 3    # Scrape in batches of 3 pages

# Database file path
DB_FILE = 'scraped_urls.db'

# ===========================
# Setup Logging
# ===========================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

# ===========================
# Database Functions
# ===========================

def setup_database(db_file=DB_FILE):
    """
    Initialize the SQLite database and create necessary tables.
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    # Table to store unique URLs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            url TEXT PRIMARY KEY,
            scraped_at TEXT
        )
    ''')
    # Table to store metadata like last scraped page per category
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    return conn

def get_metadata(conn, key):
    """
    Retrieve a metadata value by key.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
    result = cursor.fetchone()
    return int(result[0]) if result else None

def set_metadata(conn, key, value):
    """
    Set or update a metadata key-value pair.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO metadata (key, value) 
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, str(value)))
    conn.commit()

def load_existing_urls_db(conn):
    """
    Load all existing URLs from the database into a set for quick lookup.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM urls")
    return set(row[0] for row in cursor.fetchall())

def save_urls_db(conn, urls):
    """
    Save a list of new URLs into the database with the current timestamp.
    """
    cursor = conn.cursor()
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    cursor.executemany("INSERT OR IGNORE INTO urls (url, scraped_at) VALUES (?, ?)", 
                       [(url, current_time) for url in urls])
    conn.commit()

# ===========================
# Selenium WebDriver Setup
# ===========================

def setup_driver():
    """
    Initialize and return a Selenium WebDriver with configured options.
    """
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument('--log-level=3')  # Suppress logs
    chrome_options.add_argument("--window-size=1920x1080")
    # Optional: Specify the path to chromedriver if not in PATH
    # return webdriver.Chrome(executable_path='/path/to/chromedriver', options=chrome_options)
    return webdriver.Chrome(options=chrome_options)

# ===========================
# Scraping Functions
# ===========================

def scrape_single_page(page_number, base_url, retries=3):
    """
    Scrape a single page of a given category and return the list of article URLs.
    Implements retry logic in case of transient failures.
    """
    attempt = 0
    while attempt < retries:
        driver = setup_driver()
        all_links = []
        try:
            # Random delay between 1 to 3 seconds to mimic human behavior
            time.sleep(random.uniform(1, 3))
            
            current_page_url = f"{base_url}/page/{page_number}/"
            logging.info(f"[{base_url}] Visiting page: {current_page_url}")
            driver.get(current_page_url)

            # Check if the page exists by searching for a "No articles found" message
            if "No articles found" in driver.page_source:
                logging.info(f"[{base_url}] Page {page_number} does not exist or has no articles.")
                return all_links  # Empty list

            # Wait until all article links are loaded
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article a.mask-img"))
            )

            # Find all article links
            articles = driver.find_elements(By.CSS_SELECTOR, "article a.mask-img")
            article_links = [article.get_attribute("href") for article in articles]
            all_links.extend(article_links)

            logging.info(f"[{base_url}] Page {page_number}: Found {len(article_links)} links.")
            break  # Exit the retry loop if successful

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            attempt += 1
            logging.error(f"[{base_url}] Error on page {page_number} (Attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                logging.error(f"[{base_url}] Failed to scrape page {page_number} after {retries} attempts.")
        finally:
            driver.quit()
    return all_links

def scrape_articles_in_batches(conn, base_url, max_pages=10):
    """
    Scrape a specified number of pages for a given category in batches.
    """
    all_links = load_existing_urls_db(conn)
    logging.info(f"[{base_url}] Loaded {len(all_links)} existing links from database.")

    # Define a unique metadata key for tracking last scraped page per category
    metadata_key = f"last_scraped_page:{base_url}"
    last_scraped_page = get_metadata(conn, metadata_key)
    if last_scraped_page is None:
        last_scraped_page = 0  # Start from page 1 if not set
    logging.info(f"[{base_url}] Last scraped page: {last_scraped_page}")

    # Define the range of pages to scrape in this run
    start_page = last_scraped_page + 1
    end_page = start_page + max_pages - 1  # e.g., 1 to 10

    logging.info(f"[{base_url}] Scraping pages from {start_page} to {end_page}")

    # Initialize a ThreadPoolExecutor for concurrent page scraping
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        for current_start in range(start_page, end_page + 1, BATCH_SIZE):
            current_end = min(current_start + BATCH_SIZE - 1, end_page)
            logging.info(f"[{base_url}] Scraping batch: Pages {current_start} to {current_end}")
            
            # Submit scraping tasks for the current batch
            future_to_page = {
                executor.submit(scrape_single_page, page, base_url): page 
                for page in range(current_start, current_end + 1)
            }

            # Process completed scraping tasks
            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    new_links = future.result()
                    if new_links:
                        # Filter out URLs that have already been scraped
                        filtered_links = [link for link in new_links if link not in all_links]
                        if filtered_links:
                            all_links.update(filtered_links)
                            save_urls_db(conn, filtered_links)
                            logging.info(f"[{base_url}] Page {page}: {len(filtered_links)} new links added.")
                        else:
                            logging.info(f"[{base_url}] Page {page}: No new links found.")
                    else:
                        logging.info(f"[{base_url}] Page {page}: No links found.")
                except Exception as exc:
                    logging.error(f"[{base_url}] Page {page} generated an exception: {exc}")

    # Update the last scraped page number in the metadata table
    set_metadata(conn, metadata_key, end_page)
    logging.info(f"[{base_url}] Updated last scraped page to: {end_page}")

    logging.info(f"[{base_url}] Total unique links collected: {len(all_links)}")

# ===========================
# Main Function
# ===========================

def main():
    """
    Main function to initiate scraping for all categories.
    """
    # Initialize the database connection
    conn = setup_database(DB_FILE)

    try:
        # Iterate through each category and perform scraping
        for base_url in BASE_URLS:
            scrape_articles_in_batches(conn, base_url, max_pages=MAX_PAGES_PER_CATEGORY)
    finally:
        # Ensure the database connection is closed properly
        conn.close()
        logging.info("Scraping session completed.")

if __name__ == "__main__":
    main()
