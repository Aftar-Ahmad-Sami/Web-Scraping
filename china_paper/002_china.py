import csv
import logging
import time
import concurrent.futures
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scrapy.http import HtmlResponse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
OUTPUT_FILE = '0021_china.csv'
MAX_WORKERS = 7
TIMEOUT = 20
SLEEP_TIME = 1

START_URLS = [
    "https://bengali.cri.cn/index.shtml",
    "https://bengali.cri.cn/news/index.shtml",
    "https://bengali.cri.cn/currentevents/index.shtml",
    "https://bengali.cri.cn/comment/index.shtml",
    "https://bengali.cri.cn/topic/index.shtml",
    "https://bengali.cri.cn/speciallist/index.shtml"
]

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=chrome_options)

def scrape_page(url):
    driver = setup_driver()
    try:
        driver.get(url)
        time.sleep(SLEEP_TIME)  # Wait for dynamic content to load
        
        logging.info(f"Scraping page: {url}")
        
        response = HtmlResponse(url=url, body=driver.page_source, encoding='utf-8')
        
        all_urls = response.css('li div.text a::attr(href)').getall()
        
        filtered_urls = [
            urljoin(url, u) for u in all_urls 
            if not (u.endswith('/photo/index.shtml') or u.endswith('/video_list/index.shtml'))
        ]
        
        logging.info(f"Found {len(filtered_urls)} valid URLs on this page")
        
        next_page_url = get_next_page_url(driver)
        
        return filtered_urls, next_page_url
    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        return [], None
    finally:
        driver.quit()

def get_next_page_url(driver):
    try:
        next_button = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "li.nextPage a"))
        )
        return next_button.get_attribute('href')
    except:
        logging.info("No more pages to scrape.")
        return None

def save_urls(urls, output_file):
    try:
        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for url in urls:
                writer.writerow([url])
                logging.info(f"Saved URL: {url}")
    except IOError as e:
        logging.error(f"Error saving to file: {str(e)}")

def main():
    urls_to_scrape = START_URLS.copy()
    all_scraped_urls = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while urls_to_scrape:
            future_to_url = {executor.submit(scrape_page, url): url for url in urls_to_scrape}
            urls_to_scrape.clear()

            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    scraped_urls, next_page_url = future.result()
                    new_urls = set(scraped_urls) - all_scraped_urls
                    all_scraped_urls.update(new_urls)
                    save_urls(new_urls, OUTPUT_FILE)
                    
                    if next_page_url and next_page_url not in all_scraped_urls:
                        urls_to_scrape.append(next_page_url)
                except Exception as exc:
                    logging.error(f'{url} generated an exception: {exc}')

    logging.info(f"Scraping completed. Total URLs scraped: {len(all_scraped_urls)}")

if __name__ == "__main__":
    main()