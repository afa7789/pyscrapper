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

class MarketRoxoScraperSeleniumAuto:
    def __init__(self, base_url, log_callback, headless=True, proxy=None, use_webdriver_manager=True):
        """Initializes the Selenium scraper with automatic ChromeDriver management."""
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        
        self.base_url = base_url
        self.delay = 25
        self.log_callback = log_callback
        self.driver = None
        self.headless = headless
        self.proxy = proxy
        self.use_webdriver_manager = use_webdriver_manager
        
        self._setup_driver()
        self.log_callback(f"🔍 Debug: MarketRoxoScraperSeleniumAuto initialized")

    def _setup_driver(self):
        """Sets up the Chrome WebDriver with automatic driver management."""
        chrome_options = Options()
        
        # Essential options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Performance optimizations
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Anti-detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        
        # Headless mode
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        # Proxy configuration
        if self.proxy:
            chrome_options.add_argument(f"--proxy-server={self.proxy}")
        
        # Try different approaches to initialize WebDriver
        approaches = []
        
        # Approach 1: WebDriver Manager (automatic)
        if self.use_webdriver_manager:
            approaches.append(("WebDriver Manager", self._setup_with_webdriver_manager, chrome_options))
        
        # Approach 2: System ChromeDriver
        approaches.append(("System ChromeDriver", self._setup_with_system_driver, chrome_options))
        
        # Approach 3: Chromium browser as fallback
        approaches.append(("Chromium Browser", self._setup_with_chromium, chrome_options))
        
        for approach_name, setup_func, options in approaches:
            try:
                self.log_callback(f"🔧 Trying {approach_name}...")
                self.driver = setup_func(options)
                
                if self.driver:
                    # Configure timeouts
                    self.driver.implicitly_wait(10)
                    self.driver.set_page_load_timeout(30)
                    
                    # Remove webdriver property if possible
                    try:
                        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    except:
                        pass
                    
                    self.log_callback(f"✅ {approach_name} initialized successfully")
                    return
                    
            except Exception as e:
                self.log_callback(f"❌ {approach_name} failed: {e}")
                continue
        
        # If all approaches failed
        raise RuntimeError("Failed to initialize WebDriver with all available methods")

    def _setup_with_webdriver_manager(self, options):
        """Setup using webdriver-manager (automatic ChromeDriver download)"""
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except ImportError:
            self.log_callback("📦 webdriver-manager not installed. Install with: pip3 install webdriver-manager")
            return None
        except Exception as e:
            self.log_callback(f"WebDriver Manager error: {e}")
            return None

    def _setup_with_system_driver(self, options):
        """Setup using system ChromeDriver"""
        return webdriver.Chrome(options=options)

    def _setup_with_chromium(self, options):
        """Setup using Chromium browser"""
        # Try to use chromium-browser instead of google-chrome
        options.binary_location = "/usr/bin/chromium-browser"
        return webdriver.Chrome(options=options)

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

# Test the scraper
if __name__ == "__main__":
    def log_callback(message):
        print(f"[LOG] {message}")
    
    # Test with automatic driver management
    with MarketRoxoScraperSeleniumAuto(
        base_url="https://www.olx.com.br",
        log_callback=log_callback,
        headless=True,
        use_webdriver_manager=True
    ) as scraper:
        
        keywords = ["technogym"]
        ads = scraper.scrape(keywords, [], max_pages=1, save_page=True)
        
        print(f"Total ads found: {len(ads)}")
        for ad in ads[:3]:
            print(f"Title: {ad['title']}")
            print(f"URL: {ad['url']}")
            print("-" * 50)