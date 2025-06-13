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
        with MarketRoxoScraperSelenium(base_url, log_callback, proxies=proxies, use_selenium=False) as scraper:
            print("Scraper initialized successfully (without Selenium for this test).")
            print("Attempting to scrape a dummy page using requests fallback...")
            # This will use the requests fallback, as use_selenium is set to False
            # You can change use_selenium to True to test Selenium setup if you have a proper environment
            page_content = scraper._get_page_content_requests(scraper.base_url+"/brasil?q=technogym+spinning+schwinn+indoor+concept2+bike+bicicleta")
            if page_content:
                print(f"Successfully retrieved content (first 200 chars):\n{page_content[:200]}...")
            else:
                print("Failed to retrieve content.")

    except Exception as e:
        print(f"An error occurred during scraper initialization or operation: {e}")

    print("Test finished.")

