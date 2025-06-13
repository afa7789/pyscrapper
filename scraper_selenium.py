import tempfile
import os
import random
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import pdb # Importar pdb

# Import the original scraper (assuming it exists and is correct)
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
        self.temp_dir = None

        self.headers.update({
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        })

        self.delay = random.randint(20, 35)

        # Ensure no previous driver is running from *this instance*
        if self.use_selenium:
            self._setup_selenium() # Calls the setup method


    def _setup_selenium(self):
        """Sets up Chrome WebDriver with stealth options and robust error handling."""
        self.log_callback("⚙️ Iniciando setup do Selenium...")
        
        try:
            # --- START: New cleanup logic at the beginning of _setup_selenium ---
            if self.driver: # Check if a driver is already instantiated in this object
                self.log_callback("🧹 Tentando fechar WebDriver existente antes de iniciar novo...")
                try:
                    self.driver.quit()
                    self.driver = None # Clear the reference
                    self.log_callback("✅ WebDriver existente fechado com sucesso.")
                except Exception as e:
                    self.log_callback(f"⚠️ Aviso: Erro ao tentar fechar WebDriver existente: {e}")
            # --- END: New cleanup logic ---

            chrome_options = Options()

            # CONFIGURAÇÃO MÍNIMA NECESSÁRIA (descomente estas linhas)
            self.temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            self.log_callback(f"📁 Diretório temporário criado: {self.temp_dir}")
            
            # Argumentos básicos obrigatórios para funcionar
            chrome_options.add_argument("--headless")  # Executar sem interface gráfica
            chrome_options.add_argument("--no-sandbox")  # Necessário para root
            chrome_options.add_argument("--disable-dev-shm-usage")  # Evita problemas de memória
            chrome_options.add_argument("--disable-gpu")  # Desabilita GPU para headless
            chrome_options.add_argument("--disable-web-security")  # Para evitar problemas CORS
            chrome_options.add_argument(f"--user-data-dir={self.temp_dir}")  # Diretório temporário
            
            # User-Agent (opcional mas recomendado)
            user_agent = self.headers.get('User-Agent', 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36')
            chrome_options.add_argument(f"--user-agent={user_agent}")
            self.log_callback(f"ℹ️ User-Agent configurado: {user_agent[:50]}...")

            # Opções experimentais básicas
            try:
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                self.log_callback("✅ Opções experimentais configuradas.")
            except Exception as e:
                self.log_callback(f"⚠️ Aviso: Erro ao configurar opções experimentais: {e}")

            # Debug: verificar valores antes da inicialização
            self.log_callback(f"🔍 Debug - Tipo de proxies: {type(self.proxies)}")
            self.log_callback(f"🔍 Debug - Valor de proxies: {self.proxies}")

            # Initialize WebDriver with enhanced error handling
            self.log_callback("🔄 Inicializando WebDriver...")
            
            try:
                # pdb.set_trace()  # <-- COMENTE ESTA LINHA
                self.driver = webdriver.Chrome(options=chrome_options)
                self.log_callback("✅ WebDriver inicializado com sucesso")
                
            except WebDriverException as driver_error:
                self.log_callback(f"❌ Erro ao inicializar WebDriver (WebDriverException): {driver_error}")
                self.log_callback(f"🔍 Debug - Mensagem da WebDriverException: {driver_error.msg}")
                self.log_callback(f"🔍 Debug - Argumentos da WebDriverException: {driver_error.args}")
                raise
            except Exception as e:
                self.log_callback(f"❌ Erro inesperado ao inicializar WebDriver: {e}")
                self.log_callback(f"🔍 Tipo do erro: {type(e).__name__}")
                self.log_callback(f"🔍 Debug - Valor de 'e': {e}")
                raise

            # Set additional properties (anti-detection script)
            try:
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.log_callback("✅ Script anti-detecção executado")
            except Exception as script_error:
                self.log_callback(f"⚠️ Aviso: Erro ao executar script anti-detecção: {script_error}")

            # Set timeouts
            try:
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(120)
                self.log_callback("✅ Timeouts configurados")
            except Exception as timeout_error:
                self.log_callback(f"⚠️ Aviso: Erro ao configurar timeouts: {timeout_error}")

            # Pular teste de proxy por enquanto
            self.log_callback("ℹ️ Teste de proxy pulado (proxy desabilitado)")

            self.log_callback("✅ Selenium WebDriver configurado completamente")

        except Exception as e:
            self.log_callback(f"❌ Erro crítico ao configurar Selenium: {e}")
            self.log_callback(f"🔍 Tipo do erro: {type(e).__name__}")
            self.log_callback(f"🔍 Debug - Tipo de proxies: {type(self.proxies)}")
            self.log_callback(f"🔍 Debug - Valor de proxies: {self.proxies}")
            
            # Ensure cleanup on failure
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    self.driver = None # Important to clear the reference
                except:
                    pass
            
            self.use_selenium = False
            self.driver = None
            raise # Re-raise the exception to terminate the program on critical setup failure

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

                driver = self.driver
                driver.set_page_load_timeout(page_load_timeout)
                driver.get(url)

                WebDriverWait(driver, page_load_timeout).until(
                    lambda d: d.execute_script(
                        "return document.readyState") == "complete"
                )

                page_source = driver.page_source.lower()
                if any(s in page_source for s in ["cloudflare", "checking your browser", "cf-browser-verification"]):
                    self.log_callback(
                        "🔒 Detectado desafio Cloudflare. Aguardando resolução...")

                    time.sleep(15)

                    try:
                        WebDriverWait(driver, cloudflare_timeout).until(
                            lambda d: "cloudflare" not in d.page_source.lower()
                        )
                        self.log_callback("✅ Desafio Cloudflare resolvido.")
                    except TimeoutException:
                        self.log_callback(
                            "⏰ Timeout no Cloudflare. Tentando continuar...")

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
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                self.log_callback(f"🗑️ Diretório temporário removido: {self.temp_dir}")
            except Exception as e:
                self.log_callback(f"⚠️ Erro ao remover diretório temporário: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()