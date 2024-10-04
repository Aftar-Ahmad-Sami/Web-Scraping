import time
import csv
import logging
import os
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
    chrome_options.add_argument("--headless=new")  # New headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options)

def load_existing_urls(csv_file='scraped_urls.csv'):
    if not os.path.exists(csv_file):
        return set()
    
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        return set(row[0] for row in reader)

def save_urls(urls, csv_file='scraped_urls.csv'):
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        for url in urls:
            writer.writerow([url, time.strftime('%Y-%m-%d %H:%M:%S')])

def scrape_single_page(page_number, base_url):
    driver = setup_driver()
    all_links = []
    try:
        current_page_url = f"{base_url}/page/{page_number}/"
        logging.info(f"Visiting page: {current_page_url}")
        driver.get(current_page_url)

        # Wait for articles to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article a.mask-img"))
        )

        # Scrape article links
        articles = driver.find_elements(By.CSS_SELECTOR, "article a.mask-img")
        article_links = [article.get_attribute("href") for article in articles]
        all_links.extend(article_links)

        logging.info(f"Page {page_number}: Found {len(article_links)} links.")

    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
        logging.error(f"Error on page {page_number}: {e}")
    finally:
        driver.quit()
        return all_links

def scrape_articles_in_batches(base_url, max_pages=50):
    # Load previously collected URLs
    all_links = load_existing_urls()
    logging.info(f"Loaded {len(all_links)} existing links from CSV file.")

    # Break the pages into batches and scrape them concurrently
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        for start_page in range(1, max_pages + 1, BATCH_SIZE):
            end_page = min(start_page + BATCH_SIZE - 1, max_pages)
            logging.info(f"Scraping batch: Pages {start_page} to {end_page}")
            
            # Submit each page in the current batch to the ThreadPoolExecutor
            future_to_page = {executor.submit(scrape_single_page, page, base_url): page for page in range(start_page, end_page + 1)}

            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    new_links = future.result()
                    if new_links:
                        # Filter new links and save them
                        filtered_links = [link for link in new_links if link not in all_links]
                        if filtered_links:
                            all_links.update(filtered_links)
                            save_urls(filtered_links)
                        logging.info(f"Page {page}: {len(filtered_links)} new links added.")
                    else:
                        logging.info(f"Page {page}: No new links found.")

                except Exception as exc:
                    logging.error(f"Page {page} generated an exception: {exc}")

    logging.info(f"Total unique links collected: {len(all_links)}")

def main():
    base_url = "https://sharebiz.net/category/national-news"
    scrape_articles_in_batches(base_url, max_pages=100)  # Adjust max_pages as needed

if __name__ == "__main__":
    main()
