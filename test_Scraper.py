from scraper_selenium import MarketRoxoScraperSelenium
from dotenv import load_dotenv
import os
import sys

def log_callback(message):
    print(f"[LOG] {message}")

def test_basic_selenium():
    """Test basic Selenium functionality"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        print("🧪 Testing basic Selenium setup...")
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://www.google.com")
        title = driver.title
        driver.quit()
        
        print(f"✅ Basic Selenium test passed! Title: {title}")
        return True
        
    except Exception as e:
        print(f"❌ Basic Selenium test failed: {e}")
        return False

def main():
    load_dotenv()
    base_url = os.getenv("BASE_URL", "https://www.olx.com.br")
    
    print(f"🔍 Debug - BASE_URL: {base_url}")
    
    # First, test basic Selenium functionality
    if not test_basic_selenium():
        print("\n💡 Suggestions:")
        print("1. Run the diagnostic script: python3 chrome_diagnostic.py")
        print("2. Update ChromeDriver to match Chrome version")
        print("3. Try: sudo apt update && sudo apt install chromium-chromedriver")
        return
    
    print("\nInitializing MarketRoxo Selenium scraper...")
    
    # Try different configurations
    configs = [
        {"headless": True, "description": "Headless mode"},
        {"headless": False, "description": "Visible browser mode"},
    ]
    
    for config in configs:
        try:
            print(f"\n🧪 Testing with {config['description']}...")
            
            with MarketRoxoScraperSelenium(
                base_url=base_url,
                log_callback=log_callback,
                headless=config["headless"],
                proxy=None
            ) as scraper:
                
                print(f"✅ Scraper initialized successfully with {config['description']}.")
                
                # Quick test with a simple search
                print("\n--- Testing with 'technogym' ---")
                keywords = ["technogym"]
                negative_keywords = []
                
                ads = scraper.scrape(
                    keywords=keywords,
                    negative_keywords_list=negative_keywords,
                    max_pages=1,
                    save_page=True  # Save for debugging
                )
                
                if ads:
                    print(f"✅ Found {len(ads)} ads for 'technogym':")
                    for i, ad in enumerate(ads[:3], 1):  # Show first 3 ads
                        print(f"{i}. Title: {ad['title']}")
                        print(f"   URL: {ad['url']}")
                        print("-" * 50)
                else:
                    print("ℹ️  No ads found for 'technogym', but scraper worked!")
                
                print(f"✅ Test successful with {config['description']}!")
                return  # Exit on first successful test
                
        except Exception as e:
            print(f"❌ Error with {config['description']}: {type(e).__name__}: {str(e)}")
            continue
    
    print("\n❌ All configurations failed!")
    print("\n🔧 Troubleshooting steps:")
    print("1. Check Chrome and ChromeDriver versions:")
    print("   google-chrome --version")
    print("   chromedriver --version")
    print("2. Run diagnostic script: python3 chrome_diagnostic.py")
    print("3. Update ChromeDriver manually")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nTest finished.")