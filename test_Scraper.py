from scraper_selenium import MarketRoxoScraperSelenium
from dotenv import load_dotenv
import os

def log_callback(message):
    print(message)

if __name__ == "__main__":
    load_dotenv() # Load environment variables from .env file

    base_url = os.getenv("BASE_URL")  # Default to example.com if not set
    
    # Get proxy information from environment variables
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")

    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    print("Initializing scraper...")
    try:
        with MarketRoxoScraperSelenium(base_url, log_callback, proxies=proxies) as scraper:
            print("Scraper initialized successfully with Selenium.")
            # Now, call a method that uses Selenium, e.g., the scrape method
            keywords = ["technogym"]
            ads = scraper.scrape(keywords, [], max_pages=1)
            if ads:
                print(f"Found {len(ads)} ads using Selenium.")
            else:
                print("No ads found using Selenium.")

    except Exception as e:
        print(f"An error occurred during scraper initialization or operation: {e}")

    print("Test finished.")

