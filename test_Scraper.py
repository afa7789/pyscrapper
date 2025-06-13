from scraper_selenium import MarketRoxoScraperSelenium
from dotenv import load_dotenv
import os

def log_callback(message):
    print(message)

if __name__ == "__main__":
    load_dotenv()

    base_url = os.getenv("BASE_URL")
    
    # Get proxy information from environment variables
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")

    # Debug: Print the actual values and types
    print(f"🔍 Debug - BASE_URL: {base_url} (type: {type(base_url)})")
    print(f"🔍 Debug - HTTP_PROXY: {http_proxy} (type: {type(http_proxy)})")
    print(f"🔍 Debug - HTTPS_PROXY: {https_proxy} (type: {type(https_proxy)})")

    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    print(f"🔍 Debug - Final proxies dict: {proxies}")
    print(f"🔍 Debug - Proxies type: {type(proxies)}")
    
    # Additional debug: Check if any values are integers
    for key, value in proxies.items():
        print(f"🔍 Debug - proxies['{key}'] = {value} (type: {type(value)})")

    print("Initializing scraper...")
    try:
        # Try to initialize without context manager first to get better error info
        scraper = MarketRoxoScraperSelenium(base_url, log_callback, proxies=proxies)
        print("✅ Scraper object created successfully")
        
        # Now try to enter the context
        with scraper:
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
        
        # Try to get more specific information about where the error occurs
        import traceback
        print("🔍 Full traceback:")
        traceback.print_exc()

    print("Test finished.")