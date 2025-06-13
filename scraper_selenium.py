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

    def __init__(self, base_url, log_callback, proxies="", use_selenium=True):
        """
        Initialize the Selenium scraper by calling parent constructor
        and adding Selenium-specific setup.
        """
        super().__init__(log_callback, base_url, proxies)

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
             """Sets up Chrome WebDriver with stealth options and robust error handling."""
        try:
            chrome_options = Options()

            # Basic Chrome options (keep these as they are)
            temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            chrome_options.add_argument(f"--user-data-dir={temp_dir}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            # Removed redundant --disable-web-security, keeping the other one if necessary for other reasons.
            # If you don't explicitly need it, you can remove both.
            # For proxy, typically --ignore-certificate-errors is more relevant.
            # chrome_options.add_argument("--disable-web-security") # Consider removing if not strictly needed
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")

            # Set user agent
            chrome_options.add_argument(f"--user-agent={self.headers['User-Agent']}")

            # Experimental options (keep as is)
            try:
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
            except Exception as e:
                self.log_callback(f"⚠️ Aviso: Erro ao configurar opções experimentais: {e}")

            # --- PROXY CONFIGURATION FIX ---
            if self.proxies and isinstance(self.proxies, dict) and self.proxies.get('http'):
                proxy_full_url = self.proxies['http'] # Store the full URL for logging/debugging
                self.log_callback(f"🔗 Proxy original fornecido: {proxy_full_url}")

                try:
                    # Extract only the host:port part for the --proxy-server argument
                    # This assumes your IP is whitelisted on the proxy provider's side.
                    if '@' in proxy_full_url:
                        # If credentials are present, strip them
                        proxy_host_port = proxy_full_url.split('@')[-1]
                    else:
                        proxy_host_port = proxy_full_url

                    if proxy_host_port.startswith('http://'):
                        proxy_server_argument = proxy_host_port[7:] # Remove 'http://' prefix
                    else:
                        proxy_server_argument = proxy_host_port # Use as is

                    chrome_options.add_argument(f"--proxy-server={proxy_server_argument}")

                    # These arguments are still good to include for proxy usage
                    chrome_options.add_argument("--ignore-certificate-errors")
                    chrome_options.add_argument("--ignore-ssl-errors")
                    chrome_options.add_argument("--allow-running-insecure-content")

                    self.log_callback(f"✅ Proxy configurado para Selenium (esperando IP Whitelist): {proxy_server_argument}")

                except Exception as proxy_error:
                    self.log_callback(f"⚠️ Erro ao processar string do proxy para argumento: {proxy_error}")
                    # You might want to raise an error here if proxy is critical,
                    # or set self.use_selenium = False

            elif self.proxies and self.proxies != "":
                self.log_callback(f"⚠️ Formato de proxy inválido ou ausente: {type(self.proxies)} - {self.proxies}")
            # --- END PROXY CONFIGURATION FIX ---


            # Initialize WebDriver with enhanced error handling
            self.log_callback("🔄 Inicializando WebDriver...")

            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.log_callback("✅ WebDriver inicializado com sucesso")
            except WebDriverException as driver_error:
                self.log_callback(f"❌ Erro ao inicializar WebDriver (WebDriverException): {driver_error}")
                raise driver_error
            except Exception as e:
                self.log_callback(f"❌ Erro inesperado ao inicializar WebDriver: {e}")
                raise e

            # Set additional properties (keep as is)
            try:
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.log_callback("✅ Script anti-detecção executado")
            except Exception as script_error:
                self.log_callback(f"⚠️ Aviso: Erro ao executar script anti-detecção: {script_error}")

            # Set timeouts (keep as is)
            try:
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(120)
                self.log_callback("✅ Timeouts configurados")
            except Exception as timeout_error:
                self.log_callback(f"⚠️ Aviso: Erro ao configurar timeouts: {timeout_error}")

            # Test proxy if configured (adjust test URL for easier IP verification)
            if self.proxies and isinstance(self.proxies, dict) and self.proxies.get('http'):
                try:
                    self.log_callback("🔍 Testando conexão com proxy...")
                    # Use ipify.org for a simple JSON IP response
                    self.driver.get("https://api.ipify.org?format=json")

                    # Wait for the body element to be present, indicating the page has loaded
                    # (Adjusting from httpbin.org/ip to ipify.org which returns JSON directly)
                    WebDriverWait(self.driver, 30).until(
                        lambda d: d.find_element(By.TAG_NAME, "body")
                    )

                    ip_info_json = self.driver.find_element(By.TAG_NAME, "body").text
                    self.log_callback(f"🌐 Resposta do teste de IP: {ip_info_json}")

                    import json
                    try:
                        parsed_ip_info = json.loads(ip_info_json)
                        if "ip" in parsed_ip_info:
                            self.log_callback(f"✅ Teste de IP realizado com sucesso. IP via proxy: {parsed_ip_info['ip']}")
                        else:
                            self.log_callback("⚠️ Resposta do teste de IP não esperada. Não contém 'ip'.")
                    except json.JSONDecodeError:
                         self.log_callback(f"⚠️ Não foi possível decodificar JSON do teste de IP: {ip_info_json}")

                except Exception as test_error:
                    self.log_callback(f"⚠️ Não foi possível testar proxy: {test_error}")
                    # Don't fail the whole setup for proxy test failure

            self.log_callback("✅ Selenium WebDriver configurado completamente")

        except Exception as e:
            self.log_callback(f"❌ Erro crítico ao configurar Selenium: {e}")
            self.log_callback(f"🔍 Tipo do erro: {type(e).__name__}")
            self.log_callback(f"🔍 Debug - Tipo de proxies: {type(self.proxies)}")
            self.log_callback(f"🔍 Debug - Valor de proxies: {self.proxies}")

            # Try to clean up if driver was partially created
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except:
                    pass

            self.use_selenium = False
            self.driver = None

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
                    self.log_callback(
                        f"❌ Não foi possível obter conteúdo da página {page}")
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

                new_ads = self._extract_ads(
                    soup, keywords, negative_keywords_list or [])
                if new_ads:
                    self.log_callback(
                        f"✅ Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.log_callback(
                        f"⚪ Nenhum anúncio relevante encontrado na página {page}.")

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
        Gets page content using Selenium with retry logic and Cloudflare handling.
        """
        if not self.use_selenium or not self.driver:
            self.log_callback(
                "⚠️ Selenium não configurado. Não é possível obter conteúdo.")
            return None

        max_retries = 10
        delay_between_retries = 15  # seconds
        page_load_timeout = 120  # seconds
        cloudflare_timeout = 45  # seconds

        for attempt in range(1, max_retries + 1):
            driver = None
            try:
                self.log_callback(
                    f"🔄 Tentativa {attempt}/{max_retries}: Carregando {url}")

                # Use existing driver or create new one if needed
                driver = self.driver
                driver.set_page_load_timeout(page_load_timeout)
                driver.get(url)

                # Wait for page to be completely loaded
                WebDriverWait(driver, page_load_timeout).until(
                    lambda d: d.execute_script(
                        "return document.readyState") == "complete"
                )

                # Check for Cloudflare challenge
                page_source = driver.page_source.lower()
                if any(s in page_source for s in ["cloudflare", "checking your browser", "cf-browser-verification"]):
                    self.log_callback(
                        "🔒 Detectado desafio Cloudflare. Aguardando resolução...")

                    # Wait additional time for Cloudflare
                    time.sleep(15)

                    try:
                        WebDriverWait(driver, cloudflare_timeout).until(
                            lambda d: "cloudflare" not in d.page_source.lower()
                        )
                        self.log_callback("✅ Desafio Cloudflare resolvido.")
                    except TimeoutException:
                        self.log_callback(
                            "⏰ Timeout no Cloudflare. Tentando continuar...")

                # Success - return page source
                content = driver.page_source
                self.log_callback(
                    f"✅ Tentativa {attempt}/{max_retries}: Página carregada com sucesso")
                return content

            except TimeoutException as e:
                self.log_callback(
                    f"⏰ Tentativa {attempt}/{max_retries}: Timeout ao carregar {url} - {e}")
                if attempt < max_retries:
                    self.log_callback(
                        f"⏳ Aguardando {delay_between_retries}s antes da próxima tentativa...")
                    time.sleep(delay_between_retries)

            except Exception as e:
                self.log_callback(
                    f"❌ Tentativa {attempt}/{max_retries} falhou com erro: {e}")
                if attempt < max_retries:
                    self.log_callback(
                        f"⏳ Aguardando {delay_between_retries}s antes da próxima tentativa...")
                    time.sleep(delay_between_retries)

        # All retries failed
        self.log_callback(
            f"❌ Todas as {max_retries} tentativas falharam para {url}")
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
                    self.log_callback(
                        f"🎯 Encontrados {len(links)} links usando seletor: {selector}")
                    break

            if not links_found:
                self.log_callback(
                    "❌ Nenhum link de anúncio encontrado. Verifique os seletores.")
                return []

            for link in links_found:
                ad_url = link.get("href")

                ad_title = (
                    link.get("title", "") or
                    link.get("aria-label", "") or
                    link.text.strip()
                ).lower()

                if ad_url and ad_title:
                    match_positive = any(
                        keyword.lower() in ad_title for keyword in keywords)
                    match_negative = any(
                        negative.lower() in ad_title for negative in negative_keywords_list)

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
