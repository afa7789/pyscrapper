from scraper_selenium import MarketRoxoScraperSelenium
from dotenv import load_dotenv
import os

def log_callback(message):
    print(f"[LOG] {message}")

if __name__ == "__main__":
    load_dotenv()
    base_url = os.getenv("BASE_URL", "https://www.olx.com.br")
    
    # Proxy configuration (commented out but available)
    # http_proxy = os.getenv("HTTP_PROXY")
    # https_proxy = os.getenv("HTTPS_PROXY")
    # proxy = http_proxy if http_proxy else None  # For Selenium, use single proxy string
    
    print(f"🔍 Debug - BASE_URL: {base_url}")
    print("Initializing Selenium scraper...")
    
    try:
        # Using as context manager (recommended)
        with MarketRoxoScraperSelenium(
            base_url=base_url,
            log_callback=log_callback,
            proxy=None  # Set proxy if needed: "http://proxy:port"
        ) as scraper:
            
            print("✅ Scraper initialized successfully with Selenium.")
            
            # Test with technogym
            print("\n--- Testing with 'technogym' ---")
            keywords = ["technogym"]
            negative_keywords = []
            
            ads = scraper.scrape(
                keywords=keywords,
                negative_keywords_list=negative_keywords,
                max_pages=1,
                save_page=False
            )
            
            if ads:
                print(f"Found {len(ads)} ads for 'technogym':")
                for i, ad in enumerate(ads[:5], 1):  # Show first 5 ads
                    print(f"{i}. Title: {ad['title']}")
                    print(f"   URL: {ad['url']}")
                    print("-" * 50)
            else:
                print("No ads found for 'technogym'.")
            
            # Additional test with different keywords
            print("\n--- Testing with 'iphone' ---")
            keywords = ["iphone", "smartphone"]
            negative_keywords = ["quebrado", "defeito", "com defeito"]
            
            ads2 = scraper.scrape(
                keywords=keywords,
                negative_keywords_list=negative_keywords,
                max_pages=2,
                save_page=False
            )
            
            if ads2:
                print(f"Found {len(ads2)} ads for 'iphone/smartphone' (excluding broken ones):")
                for i, ad in enumerate(ads2[:3], 1):  # Show first 3 ads
                    print(f"{i}. Title: {ad['title']}")
                    print(f"   URL: {ad['url']}")
                    print("-" * 50)
            else:
                print("No ads found for 'iphone/smartphone'.")
            
            print(f"\nTotal ads found in all tests: {len(ads) + len(ads2)}")
            
    except Exception as e:
        print(f"❌ Error type: {type(e).__name__}")
        print(f"❌ Error message: {str(e)}")
        import traceback
        traceback.print_exc()

    print("Test finished.")