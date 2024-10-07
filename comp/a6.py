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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Number of threads to use per batch
MAX_THREADS = 3  # Run 3 pages concurrently
BATCH_SIZE = 3    # Scrape in batches of 3 pages

def setup_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Use standard headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options)

def setup_database(db_file='scraped_urls.db'):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            url TEXT PRIMARY KEY,
            scraped_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    return conn

def get_metadata(conn, key):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
    result = cursor.fetchone()
    return int(result[0]) if result else None

def set_metadata(conn, key, value):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO metadata (key, value) 
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, str(value)))
    conn.commit()

def load_existing_urls_db(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM urls")
    return set(row[0] for row in cursor.fetchall())

def save_urls_db(conn, urls):
    cursor = conn.cursor()
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    cursor.executemany("INSERT OR IGNORE INTO urls (url, scraped_at) VALUES (?, ?)", 
                       [(url, current_time) for url in urls])
    conn.commit()

def scrape_single_page(page_number, base_url, retries=3):
    attempt = 0
    while attempt < retries:
        driver = setup_driver()
        all_links = []
        try:
            # Random delay between 1 to 3 seconds
            time.sleep(random.uniform(1, 3))
            
            current_page_url = f"{base_url}/page/{page_number}/"
            logging.info(f"Visiting page: {current_page_url}")
            driver.get(current_page_url)

            # Check if the page exists by looking for a specific element or message
            if "No articles found" in driver.page_source:
                logging.info(f"Page {page_number} does not exist or has no articles.")
                return all_links  # Return empty list

            # Wait for articles to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article a.mask-img"))
            )

            # Scrape article links
            articles = driver.find_elements(By.CSS_SELECTOR, "article a.mask-img")
            article_links = [article.get_attribute("href") for article in articles]
            all_links.extend(article_links)

            logging.info(f"Page {page_number}: Found {len(article_links)} links.")
            break  # Exit loop if successful

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            attempt += 1
            logging.error(f"Error on page {page_number} (Attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                logging.error(f"Failed to scrape page {page_number} after {retries} attempts.")
        finally:
            driver.quit()
    return all_links

def scrape_articles_in_batches(base_url, max_pages=15, db_file='scraped_urls.db'):
    # Setup database connection
    conn = setup_database(db_file)
    all_links = load_existing_urls_db(conn)
    logging.info(f"Loaded {len(all_links)} existing links from database.")

    # Get the last scraped page number
    last_scraped_page = get_metadata(conn, 'last_scraped_page')
    if last_scraped_page is None:
        last_scraped_page = 0  # If not set, start from page 1
    logging.info(f"Last scraped page: {last_scraped_page}")

    # Define the next batch of pages to scrape
    start_page = last_scraped_page + 1
    end_page = start_page + max_pages - 1  # Adjust based on desired batch size

    logging.info(f"Scraping pages from {start_page} to {end_page}")

    # Break the pages into batches and scrape them concurrently
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        for current_start in range(start_page, end_page + 1, BATCH_SIZE):
            current_end = min(current_start + BATCH_SIZE - 1, end_page)
            logging.info(f"Scraping batch: Pages {current_start} to {current_end}")
            
            # Submit each page in the current batch to the ThreadPoolExecutor
            future_to_page = {executor.submit(scrape_single_page, page, base_url): page for page in range(current_start, current_end + 1)}

            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    new_links = future.result()
                    if new_links:
                        # Filter new links and save them
                        filtered_links = [link for link in new_links if link not in all_links]
                        if filtered_links:
                            all_links.update(filtered_links)
                            save_urls_db(conn, filtered_links)
                        logging.info(f"Page {page}: {len(filtered_links)} new links added.")
                    else:
                        logging.info(f"Page {page}: No links found.")
                except Exception as exc:
                    logging.error(f"Page {page} generated an exception: {exc}")

    # Update the last scraped page number in metadata
    set_metadata(conn, 'last_scraped_page', end_page)
    logging.info(f"Updated last scraped page to: {end_page}")

    conn.close()
    logging.info(f"Total unique links collected: {len(all_links)}")

def main():
    base_url = "https://sharebiz.net/category/national-news"
    other_links = [
        "https://sharebiz.net/category/daily-paper/first-page/",
        "https://sharebiz.net/category/international-news", 
                   
                     "https://sharebiz.net/category/sports-news",

                   ]
    scrape_articles_in_batches(base_url, max_pages=15)  # Adjust max_pages as needed

if __name__ == "__main__":
    main()
