import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service

# Import the original scraper class
# from scraper import MarketRoxoScraper

class MarketRoxoScraperSelenium:
    def __init__(self, base_url, log_callback, chrome_driver_path=None, proxy=None):
        """Initializes the Selenium scraper with the base URL and browser options."""
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        
        self.base_url = base_url
        self.delay = 25
        self.log_callback = log_callback
        self.driver = None
        self.headless = True
        self.chrome_driver_path = chrome_driver_path
        self.proxy = proxy
        
        self._setup_driver()
        self.log_callback(f"🔍 Debug: MarketRoxoScraperSelenium initialized with log_callback={log_callback}")

    def _setup_driver(self):
        """Sets up the Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        
        # Basic options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.103 Safari/537.36")
        
        # Headless mode
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Proxy configuration
        if self.proxy:
            chrome_options.add_argument(f"--proxy-server={self.proxy}")
        
        # Performance optimizations
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-javascript")  # May need to remove if site requires JS
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-extensions")
        
        try:
            if self.chrome_driver_path:
                service = Service(self.chrome_driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Assumes chromedriver is in PATH
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.log_callback("✅ Chrome WebDriver initialized successfully")
            
        except Exception as e:
            self.log_callback(f"❌ Error initializing WebDriver: {e}")
            raise

    def _build_query(self, keywords):
        """Builds a clean query string from keywords, splitting on spaces and removing duplicates."""
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = "+".join(unique_keywords)
        return query

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
        """Searches for ads across multiple MarketRoxo pages using Selenium."""
        if not self.driver:
            raise RuntimeError("WebDriver not initialized")
        
        query = self._build_query(keywords)
        ads = []
        page = 1
        
        while page <= max_pages:
            url = f"{self.base_url}/brasil?q={query}&o={page}" if page > 1 else f"{self.base_url}/brasil?q={query}"
            self.log_callback(f"Scraping página {page}... {url}")
            
            try:
                # Navigate to the URL
                self.driver.get(url)
                
                # Wait for the page to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Additional wait for dynamic content
                time.sleep(3)
                
                # Get page source and create soup
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, "html.parser")
                
                # Save page for debugging if requested
                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                    self.log_callback(f"Página {page} salva para debug.")
                
                # Check if no ads found
                if "Nenhum anúncio foi encontrado" in soup.text:
                    self.log_callback("Fim das páginas disponíveis.")
                    break
                
                # Extract ads from the page
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list)
                
                if new_ads:
                    self.log_callback(f"Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.log_callback(f"Nenhum anúncio encontrado na página {page}.")
                
                page += 1
                
                # Delay between requests
                time.sleep(self.delay)
                
            except TimeoutException:
                self.log_callback(f"Timeout na página {page}")
                break
            except WebDriverException as e:
                self.log_callback(f"Erro do WebDriver na página {page}: {e}")
                break
            except Exception as e:
                self.log_callback(f"Erro na página {page}: {e}")
                break
        
        return ads

    def _extract_ads(self, soup, keywords, negative_keywords_list=None):
        """Extracts ads from an HTML page."""
        ads = []
        
        # Find all ad links
        for link in soup.find_all("a", class_="olx-adcard__link"):
            ad_url = link.get("href")
            ad_title = link.get("title", "").lower()
            
            has_ad_url = bool(ad_url)
            has_ad_title = bool(ad_title)
            match_positive = any(keyword.lower() in ad_title for keyword in keywords)
            match_negative = any(negative.lower() in ad_title for negative in negative_keywords_list or [])
            
            if has_ad_url and has_ad_title and match_positive and not match_negative:
                full_url = urljoin(self.base_url, ad_url)
                ads.append({"title": ad_title, "url": full_url})
        
        return ads

    def _extract_ads_tested(self, filename, keywords, negative_keywords_list=None):
        """Extracts ads from an HTML file by parsing its soup."""
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
        soup = BeautifulSoup(content, "html.parser")
        return self._extract_ads(soup, keywords, negative_keywords_list)

    def _non_extracted_ads(self, soup, keywords, negative_keywords_list=None):
        """Extracts ads that do not match the keywords."""
        non_extracted_ads = []
        
        for link in soup.find_all("a", class_="olx-adcard__link"):
            ad_url = link.get("href")
            ad_title = link.get("title", "").lower()
            
            if ad_url and ad_title and (
                not any(keyword.lower() in ad_title for keyword in keywords)
                or any(negative.lower() in ad_title for negative in negative_keywords_list or [])
            ):
                full_url = urljoin(self.base_url, ad_url)
                non_extracted_ads.append({"title": ad_title, "url": full_url})
        
        return non_extracted_ads

    def _non_extracted_ads_tested(self, filename, keywords, negative_keywords_list=None):
        """Extracts ads that do not match the keywords from an HTML file."""
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
        soup = BeautifulSoup(content, "html.parser")
        return self._non_extracted_ads(soup, keywords, negative_keywords_list)

    def close(self):
        """Closes the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.log_callback("🔒 WebDriver closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

# Example usage:
if __name__ == "__main__":
    def log_callback(message):
        print(f"[LOG] {message}")
    
    # Using as context manager (recommended)
    with MarketRoxoScraperSelenium(
        base_url="https://www.olx.com.br",
        log_callback=log_callback,
        proxy=None  # Set proxy if needed: "http://proxy:port"
    ) as scraper:
        
        keywords = ["iphone", "smartphone"]
        negative_keywords = ["quebrado", "defeito"]
        
        ads = scraper.scrape(
            keywords=keywords,
            negative_keywords_list=negative_keywords,
            max_pages=3,
            save_page=False
        )
        
        print(f"Total ads found: {len(ads)}")
        for ad in ads[:5]:  # Show first 5 ads
            print(f"Title: {ad['title']}")
            print(f"URL: {ad['url']}")
            print("-" * 50)