from selenium_scraper_auto import MarketRoxoScraperSeleniumAuto
from dotenv import load_dotenv
import os

def log_callback(message):
    print(message)

if __name__ == "__main__":
    load_dotenv()
    base_url = os.getenv("BASE_URL", "https://www.olx.com.br")

    print("Initializing AUTO scraper...")
    try:        
        with MarketRoxoScraperSeleniumAuto(
            base_url=base_url, 
            log_callback=log_callback,
            headless=True,
            use_webdriver_manager=True
        ) as scraper:
            print("✅ AUTO Scraper initialized successfully with Selenium.")
            keywords = ["technogym"]
            ads = scraper.scrape(keywords, [], max_pages=1)
            if ads:
                print(f"Found {len(ads)} ads using AUTO Selenium.")
                for ad in ads[:3]:
                    print(f"Title: {ad['title']}")
                    print(f"URL: {ad['url']}")
                    print("-" * 30)
            else:
                print("No ads found using AUTO Selenium.")
    except Exception as e:
        print(f"❌ Error type: {type(e).__name__}")
        print(f"❌ Error message: {str(e)}")
        import traceback
        traceback.print_exc()

    print("Test finished.")