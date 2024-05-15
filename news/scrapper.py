import requests
from bs4 import BeautifulSoup
import pandas as pd

# URL of bdnews24 homepage (you can change it to any other legit news site)
url = 'https://bangla.bdnews24.com/'

def scrape_news(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # This part will vary depending on each website's structure:
    articles = []
    
    # Find all article containers based on inspection of HTML structure.
    items = soup.find_all('div', class_='TopLeadList') + \
            soup.find_all('div', class_='MainLead') + \
            soup.find_all('div', class_='SpCatThreeSmallList') + \
            soup.find_all('div', class_='items')

    print(f"Found {len(items)} items")
    
    for item in items:
        title_tag = item.find(['h1', 'h2'])
        if title_tag:
            title = title_tag.text.strip()
            link_tag = item.find_parent('a', href=True) or item.find('a', href=True)
            
            if link_tag:
                link_href = link_tag['href']
                if not link_href.startswith("http"):
                    # Handle relative URLs by joining them with the base URL
                    from urllib.parse import urljoin
                    link_href = urljoin(url, link_href)

                articles.append({
                    'title': title,
                    'link': link_href,
                })
    
    return articles

def main():
    print(f"Scraping {url}...")
    news_articles = scrape_news(url)

    if not news_articles:
        print("No articles found.")
        return
    
    df = pd.DataFrame(news_articles)
    
    # Save results to CSV file
    df.to_csv("bdnews24_headlines.csv", index=False)

if __name__ == "__main__":
   main()
