import time
import csv
import logging
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def scrape_articles(base_url, driver, max_retries=5):
    all_links = load_existing_urls()
    logging.info(f"Loaded {len(all_links)} existing links from CSV file.")
    
    retry_count = 0
    total_links_found = 0
    total_new_links_added = 0
    page_number = 1

    while True:
        try:
            # Construct the page URL and load the page
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
            total_links_found += len(article_links)

            # Filter new links and update the set
            new_links = [link for link in article_links if link not in all_links]
            all_links.update(new_links)
            total_new_links_added += len(new_links)
            
            logging.info(f"Found {len(article_links)} links on this page, {len(new_links)} are new.")

            # Save new links to CSV
            if new_links:
                save_urls(new_links)
            else:
                logging.info(f"No new links found on page {page_number}. Exiting.")
                break  # Exit if no new links are found on a page

            # Increment the page number
            page_number += 1

            # Check if the "Load More" button or next page exists
            try:
                load_more = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.block-loader"))
                )
                logging.info(f"Found 'Load More' button for page {page_number}.")
            except TimeoutException:
                logging.info(f"No 'Load More' button found on page {page_number}. Stopping pagination.")
                break  # Stop if no "Load More" button is found

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            retry_count += 1
            logging.warning(f"Error encountered: {e}. Retrying ({retry_count}/{max_retries})...")
            if retry_count >= max_retries:
                logging.error("Max retries reached. Exiting.")
                break
            time.sleep(10)  # Delay before retrying

    logging.info(f"Total links found across all pages: {total_links_found}")
    logging.info(f"Total new links added: {total_new_links_added}")
    logging.info(f"Total unique links collected: {len(all_links)}")

def main():
    driver = setup_driver()
    try:
        scrape_articles("https://sharebiz.net/category/national-news", driver)
    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    main()
