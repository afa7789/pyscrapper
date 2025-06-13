import tempfile
import os
import random
import time
import requests
import shutil
import atexit
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from scraper import MarketRoxoScraper

class MarketRoxoScraperSelenium(MarketRoxoScraper):
    """
    Selenium-enhanced version of MarketRoxoScraper.
    Inherits all functionality from the original scraper and overrides
    the page fetching method to use Selenium instead of requests.
    """

    def __init__(self, base_url, log_callback, proxies=None, use_selenium=True):
        """
        Initialize the Selenium scraper by calling parent constructor
        and adding Selenium-specific setup.
        """
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        self.log_callback(f"🔍 Debug: MarketRoxoScraperSelenium received log_callback={log_callback}")
        super().__init__(log_callback, base_url, proxies)
        self.log_callback(f"🔍 Debug: After super().__init__, self.log_callback={self.log_callback}")
        self.use_selenium = use_selenium
        self.driver = None
        self.temp_dir = None
        self.proxies = proxies or {}

        self.headers.update({
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        })

        self.delay = random.randint(20, 35)
        atexit.register(self.close)

        if self.use_selenium:
            self._setup_selenium()

    def _setup_selenium(self):
        """Sets up Chrome WebDriver with stealth options and robust error handling."""
        try:
            self.log_callback("⚙️ Iniciando setup do Selenium...")
            self.close()

            self.temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            self.log_callback(f"📁 Diretório temporário criado: {self.temp_dir}")

            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.temp_dir}")
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument(f"--user-agent={self.headers['User-Agent']}")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            if self.proxies and isinstance(self.proxies, dict) and self.proxies.get('http'):
                proxy_url = self.proxies['http']
                self.log_callback(f"🔗 Proxy original fornecido: {proxy_url}")
                parsed = urlparse(proxy_url)
                if parsed.hostname and parsed.port:
                    proxy_server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                    chrome_options.add_argument(f"--proxy-server={proxy_server}")
                    self.log_callback(f"✅ Proxy configurado: {proxy_server}")
                    if parsed.username and parsed.password:
                        self.log_callback("⚠️ Aviso: Autenticação de proxy pode precisar de configuração adicional (e.g., Chrome extension)")
                else:
                    self.log_callback("❌ Formato de proxy inválido")
                    raise ValueError(f"Formato de proxy inválido: {proxy_url}")

            self.log_callback("🔄 Inicializando WebDriver...")
            try:
                service = Service(ChromeDriverManager().install(), log_output="chromedriver.log")
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.log_callback("✅ WebDriver inicializado com sucesso")
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(120)
            except WebDriverException as e:
                self.log_callback(f"❌ Erro ao inicializar WebDriver: {e}")
                raise
            except Exception as e:
                self.log_callback(f"❌ Erro inesperado ao inicializar WebDriver: {e}")
                raise

            if self.proxies and isinstance(self.proxies, dict) and self.proxies.get('http'):
                try:
                    self.log_callback("🔍 Testando conexão com proxy...")
                    self.driver.get("https://api.ipify.org?format=json")
                    WebDriverWait(self.driver, 30).until(
                        lambda d: d.find_element(By.TAG_NAME, "body")
                    )
                    ip_info_text = self.driver.find_element(By.TAG_NAME, "body").text
                    self.log_callback(f"🌐 Resposta do teste de IP: {ip_info_text}")
                    ip_info_json = json.loads(ip_info_text)
                    if "ip" in ip_info_json:
                        self.log_callback(f"✅ Teste de IP realizado com sucesso. IP: {ip_info_json['ip']}")
                    else:
                        self.log_callback("⚠️ Resposta do teste de IP não esperada")
                except Exception as e:
                    self.log_callback(f"⚠️ Não foi possível testar proxy: {e}")

            self.log_callback("✅ Selenium WebDriver configurado completamente")

        except Exception as e:
            self.log_callback(f"❌ Erro crítico ao configurar Selenium: {e}")
            self.log_callback(f"🔍 Tipo do erro: {type(e).__name__}")
            self.log_callback(f"🔍 Debug - Proxies: {self.proxies}")
            self.close()
            self.use_selenium = False
            self.driver = None
            raise

    def _terminate_chrome_processes(self):
        """Terminate any lingering Chrome processes."""
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] in ['chrome', 'chromedriver']:
                    proc.terminate()
                    proc.wait(timeout=3)
                    self.log_callback(f"✅ Terminated process: {proc.info['name']}")
        except Exception as e:
            self.log_callback(f"⚠️ Erro ao terminar processos do Chrome: {e}")

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
        Gets page content using Selenium with retry logic and Cloudflare handling.
        """
        if not self.use_selenium or not self.driver:
            self.log_callback("⚠️ Selenium não configurado. Não é possível obter conteúdo.")
            return None

        max_retries = 10
        delay_between_retries = 15
        page_load_timeout = 120
        cloudflare_timeout = 45

        for attempt in range(1, max_retries + 1):
            try:
                self.log_callback(f"🔄 Tentativa {attempt}/{max_retries}: Carregando {url}")
                self.driver.set_page_load_timeout(page_load_timeout)
                self.driver.get(url)

                WebDriverWait(self.driver, page_load_timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                page_source = self.driver.page_source.lower()
                if any(s in page_source for s in ["cloudflare", "checking your browser", "cf-browser-verification"]):
                    self.log_callback("🔒 Detectado desafio Cloudflare. Aguardando resolução...")
                    time.sleep(15)
                    try:
                        WebDriverWait(self.driver, cloudflare_timeout).until(
                            lambda d: "cloudflare" not in d.page_source.lower()
                        )
                        self.log_callback("✅ Desafio Cloudflare resolvido.")
                    except TimeoutException:
                        self.log_callback("⏰ Timeout no Cloudflare. Tentando continuar...")

                content = self.driver.page_source
                self.log_callback(f"✅ Tentativa {attempt}/{max_retries}: Página carregada com sucesso")
                return content

            except TimeoutException as e:
                self.log_callback(f"⏰ Tentativa {attempt}/{max_retries}: Timeout ao carregar {url} - {e}")
                if attempt < max_retries:
                    self.log_callback(f"⏳ Aguardando {delay_between_retries}s antes da próxima tentativa...")
                    time.sleep(delay_between_retries)

            except Exception as e:
                self.log_callback(f"❌ Tentativa {attempt}/{max_retries} falhou com erro: {e}")
                if attempt < max_retries:
                    self.log_callback(f"⏳ Aguardando {delay_between_retries}s antes da próxima tentativa...")
                    time.sleep(delay_between_retries)

        self.log_callback(f"❌ Todas as {max_retries} tentativas falharam para {url}")
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
        try:
            self._terminate_chrome_processes()
            if self.driver:
                try:
                    self.driver.quit()
                    self.log_callback("🔒 Selenium WebDriver fechado.")
                except Exception as e:
                    self.log_callback(f"⚠️ Erro ao fechar WebDriver: {e}")
                self.driver = None

            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                    self.log_callback(f"🗑️ Diretório temporário removido: {self.temp_dir}")
                except Exception as e:
                    self.log_callback(f"⚠️ Erro ao remover diretório temporário: {e}")
                self.temp_dir = None
        except Exception as e:
            self.log_callback(f"⚠️ Erro durante cleanup: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()