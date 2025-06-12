import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import random

class MarketRoxoScraper:
    def __init__(self, base_url, log_callback, use_selenium=True):
        """Initializes the scraper with the base URL and headers."""
        self.base_url = base_url
        self.use_selenium = use_selenium
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        }
        self.delay = random.randint(20, 30)  # Random delay between requests
        self.log_callback = log_callback
        self.driver = None
        
        if self.use_selenium:
            self._setup_selenium()

    def _setup_selenium(self):
        """Sets up Chrome WebDriver with stealth options."""
        try:
            chrome_options = Options()

            # Create a unique temporary directory
            temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            chrome_options.add_argument(f"--user-data-dir={temp_dir}")
                
            # Stealth options to avoid detection
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")  # Faster loading
            chrome_options.add_argument("--disable-javascript")  # Try without JS first
            
            # Uncomment for headless mode (no GUI)
            chrome_options.add_argument("--headless")
            
            # User agent
            chrome_options.add_argument(f"--user-agent={self.headers['User-Agent']}")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.log_callback("Selenium WebDriver configurado com sucesso.")
            
        except Exception as e:
            self.log_callback(f"Erro ao configurar Selenium: {e}")
            self.use_selenium = False

    def _build_query(self, keywords):
        """Builds a clean query string from keywords, splitting on spaces and removing duplicates."""
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = "+".join(unique_keywords)
        return query

    def _get_page_content(self, url):
        """Gets page content using either Selenium or requests."""
        if self.use_selenium and self.driver:
            return self._get_page_selenium(url)
        else:
            return self._get_page_requests(url)

    def _get_page_selenium(self, url):
        """Gets page content using Selenium."""
        try:
            self.driver.get(url)
            
            # Wait for page to load and check for Cloudflare
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Check if we're blocked by Cloudflare
            if "cloudflare" in self.driver.page_source.lower() or "checking your browser" in self.driver.page_source.lower():
                self.log_callback("Detectado desafio Cloudflare. Aguardando...")
                
                # Wait longer for Cloudflare challenge to complete
                time.sleep(10)
                
                # Try to wait for the challenge to complete
                try:
                    WebDriverWait(self.driver, 30).until(
                        lambda driver: "cloudflare" not in driver.page_source.lower()
                    )
                except TimeoutException:
                    self.log_callback("Timeout aguardando Cloudflare. Continuando...")
            
            return self.driver.page_source
            
        except Exception as e:
            self.log_callback(f"Erro no Selenium: {e}")
            return None

    def _get_page_requests(self, url):
        """Gets page content using requests (fallback method)."""
        try:
            # Add some random headers to look more human
            session = requests.Session()
            session.headers.update(self.headers)
            
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
            
        except Exception as e:
            self.log_callback(f"Erro no requests: {e}")
            return None

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
        """Searches for ads across multiple MarketRoxo pages."""
        query = self._build_query(keywords)
        ads = []
        page = 1
        
        while page <= max_pages:
            url = f"{self.base_url}/brasil?q={query}&o={page}" if page > 1 else f"{self.base_url}/brasil?q={query}"
            self.log_callback(f"Scraping página {page}... {url}")

            try:
                page_content = self._get_page_content(url)
                
                if not page_content:
                    self.log_callback(f"Não foi possível obter conteúdo da página {page}")
                    break
                
                soup = BeautifulSoup(page_content, "html.parser")

                # Save page for debugging
                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                    self.log_callback(f"Página {page} salva para debug.")

                # Check if the page is empty
                if "Nenhum anúncio foi encontrado" in soup.text:
                    self.log_callback("Fim das páginas disponíveis.")
                    break

                # Extract ads
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list)
                if new_ads:
                    self.log_callback(f"Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.log_callback(f"Nenhum anúncio relevante encontrado na página {page}.")
                
                page += 1
                
                # Random delay to avoid detection
                delay = random.randint(self.delay, self.delay + 10)
                self.log_callback(f"Aguardando {delay} segundos...")
                time.sleep(delay)

            except Exception as e:
                self.log_callback(f"Erro na página {page}: {e}")
                break

        return ads

    def _extract_ads(self, soup, keywords, negative_keywords_list=None):
        """Extracts ads from an HTML page."""
        ads = []
        
        # Try multiple selectors as OLX might use different classes
        selectors = [
            "a.olx-adcard__link",
            "a[class*='adcard']",
            "a[data-testid*='ad-card']",
            "a[href*='/anuncio/']"
        ]
        
        links_found = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                links_found = links
                self.log_callback(f"Encontrados {len(links)} links usando seletor: {selector}")
                break
        
        if not links_found:
            self.log_callback("Nenhum link de anúncio encontrado. Verifique os seletores.")
            return ads

        for link in links_found:
            ad_url = link.get("href")
            
            # Try different ways to get the title
            ad_title = (
                link.get("title", "") or 
                link.get("aria-label", "") or
                link.text.strip()
            ).lower()

            if ad_url and ad_title:
                match_positive = any(keyword.lower() in ad_title for keyword in keywords)
                match_negative = any(negative.lower() in ad_title for negative in (negative_keywords_list or []))
                
                if match_positive and not match_negative:
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
        _non_extracted_ads = []
        
        for link in soup.find_all("a", class_="olx-adcard__link"):
            ad_url = link.get("href")
            ad_title = link.get("title", "").lower()

            if ad_url and ad_title and (
                not any(keyword.lower() in ad_title for keyword in keywords)
                or any(negative.lower() in ad_title for negative in (negative_keywords_list or []))
            ):
                full_url = urljoin(self.base_url, ad_url)
                _non_extracted_ads.append({"title": ad_title, "url": full_url})
                
        return _non_extracted_ads

    def close(self):
        """Closes the Selenium driver."""
        if self.driver:
            self.driver.quit()
            self.log_callback("Selenium WebDriver fechado.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Example usage
if __name__ == "__main__":
    def log_callback(message):
        print(f"[LOG] {message}")

    # Test with Selenium
    with MarketRoxoScraper("https://www.olx.com.br", log_callback, use_selenium=True) as scraper:
        keywords = ["bike", "indoor", "concept2"]
        negative_keywords = ["quebrada", "defeito", "peças"]
        
        ads = scraper.scrape(keywords, negative_keywords, max_pages=2, save_page=True)
        
        print(f"\nTotal de anúncios encontrados: {len(ads)}")
        for ad in ads[:5]:  # Show first 5
            print(f"- {ad['title']}")
            print(f"  URL: {ad['url']}\n")