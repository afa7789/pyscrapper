import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import cloudscraper
from fake_useragent import UserAgent
import pickle
import os

class MarketRoxoScraperCloudflare:
    def __init__(self, log_callback, base_url, proxies=""):
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        
        self.base_url = base_url
        self.log_callback = log_callback
        self.session_file = "cf_session.pkl"
        self.session_timeout = 1800  # 30 minutes
        
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.session_start_time = time.time()
        self._load_session()
        
        self.ua = UserAgent()
        self._setup_headers()
        
        self.delay_min = 30  # Increased delay
        self.delay_max = 60
        
        self.log_callback(f"🔍 MarketRoxoScraper inicializado com bypass Cloudflare")

    def _load_session(self):
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'rb') as f:
                    cookies = pickle.load(f)
                    self.scraper.cookies.update(cookies)
                    self.log_callback(f"🍪 Sessão anterior carregada com {len(cookies)} cookies")
            else:
                self.log_callback("ℹ️ Nenhum arquivo de sessão encontrado, iniciando nova sessão")
        except Exception as e:
            self.log_callback(f"⚠️ Erro ao carregar sessão: {e}")
            self._reset_session()

    def _save_session(self):
        try:
            with open(self.session_file, 'wb') as f:
                pickle.dump(self.scraper.cookies, f)
            self.log_callback(f"🍪 Sessão salva com {len(self.scraper.cookies)} cookies")
        except Exception as e:
            self.log_callback(f"⚠️ Erro ao salvar sessão: {e}")

    def _reset_session(self):
        self.log_callback("🔄 Resetando sessão...")
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.session_start_time = time.time()
        self.log_callback("✅ Nova sessão criada")

    def _is_session_expired(self):
        return (time.time() - self.session_start_time) > self.session_timeout

    def _setup_headers(self):
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }

    def _get_random_headers(self):
        headers = self.base_headers.copy()
        headers['User-Agent'] = self.ua.random
        return headers

    def _build_query(self, keywords):
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = "+".join(unique_keywords)
        return query

    def _random_delay(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        self.log_callback(f"⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _make_fallback_request(self, url, headers):
        try:
            session = requests.Session()
            session.headers.update(headers)
            response = session.get(url, timeout=30)
            response.raise_for_status()
            self.log_callback(f"✅ Fallback request bem-sucedido: {response.status_code}")
            return response
        except Exception as e:
            self.log_callback(f"❌ Fallback request falhou: {str(e)}")
            return None

    def _make_request(self, url, max_retries=3):
        if self._is_session_expired():
            self._reset_session()

        for attempt in range(max_retries):
            try:
                headers = self._get_random_headers()
                self.scraper.headers.update(headers)
                self.log_callback(f"🌐 Fazendo request para: {url}")
                self.log_callback(f"📋 Headers: {headers}")
                self.log_callback(f"🍪 Cookies: {self.scraper.cookies.get_dict()}")
                response = self.scraper.get(url, timeout=30)
                response.raise_for_status()

                if "cloudflare" in response.text.lower() and ("blocked" in response.text.lower() or "captcha" in response.text.lower()):
                    raise Exception("Bloqueado pelo Cloudflare")
                if "data-testid=\"ad-card-link\"" not in response.text and len(response.text) > 1000:
                    self.log_callback(f"⚠️ Página incompleta detectada (sem anúncios)")
                    self._reset_session()
                    raise Exception("Página incompleta sem anúncios")
                
                self.log_callback(f"✅ Request bem-sucedido: {response.status_code}")
                self._save_session()
                return response

            except Exception as e:
                self.log_callback(f"❌ Tentativa {attempt + 1} falhou: {str(e)}")
                if attempt < max_retries - 1:
                    if str(e).startswith("403") or "Página incompleta" in str(e):
                        self._reset_session()
                    time.sleep(random.uniform(60, 120))  # Increased retry delay
                else:
                    self.log_callback("🔄 Tentando fallback request...")
                    response = self._make_fallback_request(url, headers)
                    if response:
                        return response
                    raise e

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=True):
        query = self._build_query(keywords)
        ads = []
        page = 1
        
        self.log_callback(f"🚀 Iniciando scraping para: {query}")
        
        while page <= max_pages:
            url = f"{self.base_url}/brasil?q={query}&o={page}" if page > 1 else f"{self.base_url}/brasil?q={query}"
            self.log_callback(f"📄 Scraping página {page}... {url}")
            
            try:
                response = self._make_request(url)
                soup = BeautifulSoup(response.text, "html.parser")
                
                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                    self.log_callback(f"💾 Página {page} salva.")
                
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list, url)
                
                if new_ads:
                    self.log_callback(f"✅ Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.log_callback(f"⚠️ Nenhum anúncio relevante na página {page}.")
                
                page += 1
                
                if page <= max_pages:
                    self._random_delay()

                if "Nenhum anúncio foi encontrado" in soup.text or "Não encontramos nenhum resultado" in soup.text:
                    self.log_callback(f"🔚 Páginade anúncios não encotrados. url:{url}")
                    break
                
            except Exception as e:
                self.log_callback(f"💥 Erro na página {page}: {e}")
                break
        
        self.log_callback(f"🎯 Total de anúncios encontrados: {len(ads)}")
        return ads

    def _log_found_ad_to_file(self, page_url, ad_title, ad_url):
        try:
            with open("found_ads.log", "a