from scraper_selenium import MarketRoxoScraperSelenium
from dotenv import load_dotenv
import os

def log_callback(message):
    print(message)

if __name__ == "__main__":
    load_dotenv()
    base_url = os.getenv("BASE_URL", "https://www.olx.com.br")
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")

    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    print(f"🔍 Debug - BASE_URL: {base_url}")
    print(f"🔍 Debug - Proxies: {proxies}")

    print("Initializing scraper...")
    try:
        with MarketRoxoScraperSelenium(base_url, log_callback, proxies=proxies) as scraper:
            print("✅ Scraper initialized successfully with Selenium.")
            keywords = ["technogym"]
            ads = scraper.scrape(keywords, [], max_pages=1)
            if ads:
                print(f"Found {len(ads)} ads using Selenium.")
            else:
                print("No ads found using Selenium.")
    except Exception as e:
        print(f"❌ Error type: {type(e).__name__}")
        print(f"❌ Error message: {str(e)}")
        import traceback
        traceback.print_exc()

    print("Test finished.")