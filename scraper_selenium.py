import tempfile
import random
import time
import requests  # Added for _get_page_content_requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Import the original scraper
from scraper import MarketRoxoScraper


class MarketRoxoScraperSelenium(MarketRoxoScraper):
    """
    Selenium-enhanced version of MarketRoxoScraper.
    Inherits all functionality from the original scraper and only overrides
    the page fetching method to use Selenium instead of requests.
    """
    
    def __init__(self, base_url, log_callback, use_selenium=True):
        """
        Initialize the Selenium scraper by calling parent constructor
        and adding Selenium-specific setup.
        """
        super().__init__(base_url, log_callback)
        
        self.use_selenium = use_selenium
        self.driver = None
        
        self.headers.update({
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        })
        
        self.delay = random.randint(20, 35)
        
        if self.use_selenium:
            self._setup_selenium()

    def _setup_selenium(self):
        """Sets up Chrome WebDriver with stealth options."""
        try:
            chrome_options = Options()
            
            temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            chrome_options.add_argument(f"--user-data-dir={temp_dir}")
                
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            
            chrome_options.add_argument(f"--user-agent={self.headers['User-Agent']}")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.log_callback("✅ Selenium WebDriver configurado com sucesso.")
            
        except Exception as e:
            self.log_callback(f"⚠️ Erro ao configurar Selenium: {e}")
            self.use_selenium = False

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
        """
        Override the scrape method to use Selenium for page fetching.
        The core scraping logic remains the same as the parent class.
        """
        query = self._build_query(keywords)
        ads = []
        page = 1
        
        while page <= max_pages:
            url = f"{self.base_url}/brasil?q={query}&o={page}" if page > 1 else f"{self.base_url}/brasil?q={query}"
            self.log_callback(f"🔍 Scraping página {page}... {url}")

            try:
                page_content = self._get_page_content_selenium(url)
                
                if not page_content:
                    self.log_callback(f"❌ Não foi possível obter conteúdo da página {page}")
                    self.log_callback("🔄 Tentando com requests...")
                    page_content = self._get_page_content_requests(url)
                    
                    if not page_content:
                        break
                
                soup = BeautifulSoup(page_content, "html.parser")

                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                    self.log_callback(f"💾 Página {page} salva para debug.")

                if "Nenhum anúncio foi encontrado" in soup.text:
                    self.log_callback("🏁 Fim das páginas disponíveis.")
                    break

                new_ads = self._extract_ads(soup, keywords, negative_keywords_list or [])
                if new_ads:
                    self.log_callback(f"✅ Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.log_callback(f"⚪ Nenhum anúncio relevante encontrado na página {page}.")
                
                page += 1
                
                delay = random.randint(self.delay, self.delay + 15)
                self.log_callback(f"⏳ Aguardando {delay} segundos...")
                time.sleep(delay)

            except Exception as e:
                self.log_callback(f"💥 Erro na página {page}: {e}")
                break

        return ads

    def _get_page_content_selenium(self, url):
        """
        NEW METHOD: Gets page content using Selenium.
        """
        if not self.use_selenium or not self.driver:
            self.log_callback("⚠️ Selenium não configurado. Não é possível obter conteúdo.")
            return None
            
        try:
            self.driver.get(url)
            
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            page_source = self.driver.page_source.lower()
            if any(s in page_source for s in ["cloudflare", "checking your browser", "cf-browser-verification"]):
                self.log_callback("🔒 Detectado desafio Cloudflare. Aguardando resolução...")
                
                time.sleep(15)
                
                try:
                    WebDriverWait(self.driver, 45).until(
                        lambda driver: "cloudflare" not in driver.page_source.lower()
                    )
                    self.log_callback("✅ Desafio Cloudflare resolvido.")
                except TimeoutException:
                    self.log_callback("⏰ Timeout no Cloudflare. Tentando continuar...")
            
            return self.driver.page_source
            
        except Exception as e:
            self.log_callback(f"❌ Erro no Selenium: {e}")
            return None

    def _get_page_content_requests(self, url):
        """
        FALLBACK METHOD: Use requests when Selenium fails.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.log_callback(f"❌ Erro no requests: {e}")
            return None

    def _extract_ads(self, soup, keywords, negative_keywords_list=None):
        """
        Enhanced ad extraction with multiple selectors.
        """
        negative_keywords_list = negative_keywords_list or []
        try:
            ads = []
            
            selectors = [
                "a.olx-adcard__link",
                "a[class*='adcard']",
                "a[data-testid*='ad-card']",
                "a[href*='/anuncio/']",
                "a[href*='/item/']",
            ]
            
            links_found = []
            for selector in selectors:
                links = soup.select(selector)
                if links:
                    links_found = links
                    self.log_callback(f"🎯 Encontrados {len(links)} links usando seletor: {selector}")
                    break
            
            if not links_found:
                self.log_callback("❌ Nenhum link de anúncio encontrado. Verifique os seletores.")
                return []

            for link in links_found:
                ad_url = link.get("href")
                
                ad_title = (
                    link.get("title", "") or 
                    link.get("aria-label", "") or
                    link.text.strip()
                ).lower()

                if ad_url and ad_title:
                    match_positive = any(keyword.lower() in ad_title for keyword in keywords)
                    match_negative = any(negative.lower() in ad_title for negative in negative_keywords_list)
                    
                    if match_positive and not match_negative:
                        full_url = urljoin(self.base_url, ad_url)
                        ads.append({"title": ad_title, "url": full_url})

            return ads
            
        except Exception as e:
            self.log_callback(f"⚠️ Erro na extração melhorada: {e}")
            return []

    def close(self):
        """Close the Selenium driver properly."""
        if self.driver:
            try:
                self.driver.quit()
                self.log_callback("🔒 Selenium WebDriver fechado.")
            except Exception as e:
                self.log_callback(f"⚠️ Erro ao fechar WebDriver: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# if __name__ == "__main__":
#     def log_callback(message):
#         from datetime import datetime
#         print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

#     with MarketRoxoScraperSelenium("https://www.olx.com.br", log_callback) as scraper:
#         keywords = ["bike", "indoor", "concept2"]
#         negative_keywords = ["quebrada", "defeito", "peças"]
        
#         ads = scraper.scrape(keywords, negative_keywords, max_pages=2, save_page=True)
        
#         print(f"\n📊 Total de anúncios encontrados: {len(ads)}")
#         for ad in ads[:5]:
#             print(f"🎯 {ad['title']}")
#             print(f"🔗 {ad['url']}\n")