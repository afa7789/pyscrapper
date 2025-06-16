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
        
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self._load_session()
        
        self.ua = UserAgent()
        self._setup_headers()
        
        self.delay_min = 15
        self.delay_max = 35
        
        self.log_callback(f"🔍 MarketRoxoScraper inicializado com bypass Cloudflare")

    def _load_session(self):
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'rb') as f:
                    cookies = pickle.load(f)
                    self.scraper.cookies.update(cookies)
                    self.log_callback(f"🍪 Sessão anterior carregada com {len(cookies)} cookies")
        except Exception as e:
            self.log_callback(f"⚠️ Erro ao carregar sessão: {e}")

    def _save_session(self):
        try:
            with open(self.session_file, 'wb') as f:
                pickle.dump(self.scraper.cookies, f)
            self.log_callback(f"🍪 Sessão salva com {len(self.scraper.cookies)} cookies")
        except Exception as e:
            self.log_callback(f"⚠️ Erro ao salvar sessão: {e}")

    def _reset_session(self):
        self.log_callback("🔄 Resetando sessão devido a bloqueio...")
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.log_callback("✅ Nova sessão criada")

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
            'Cache-Control': 'max-age=0'
        }

    def _get_random_headers(self):
        headers = self.base_headers.copy()
        headers['User-Agent'] = self.ua.random
        if random.choice([True, False]):
            headers['X-Forwarded-For'] = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        return headers

    def _build_query(self, keywords):
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        random_word = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5))
        query = "+".join(unique_keywords) + "+" + random_word
        return query

    def _random_delay(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        self.log_callback(f"⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _make_request(self, url, max_retries=3):
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
                    raise Exception("Página incompleta sem anúncios")
                
                self.log_callback(f"✅ Request bem-sucedido: {response.status_code}")
                self._save_session()
                return response

            except Exception as e:
                self.log_callback(f"❌ Tentativa {attempt + 1} falhou: {str(e)}")
                if attempt < max_retries - 1:
                    if str(e).startswith("403"):
                        self._reset_session()
                    time.sleep(random.uniform(30, 60))
                else:
                    raise e

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
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
            with open("found_ads.log", "a", encoding="utf-8") as f:
                f.write(f"Página: {page_url}\n")
                f.write(f"Título do Anúncio: {ad_title}\n")
                f.write(f"Link do Anúncio: {ad_url}\n")
                f.write("-" * 50 + "\n")
        except Exception as e:
            self.log_callback(f"❌ Erro ao escrever no arquivo found_ads.log: {e}")

    def _extract_ads(self, soup, keywords, negative_keywords_list=None, page_url=""):
        debug = True  # Enable for detailed logging
        ads = []
        
        if debug:
            self._log_debug_info(soup, keywords, negative_keywords_list, page_url)
        
        found_links = self._find_ad_links(soup, debug)
        if not found_links:
            self._handle_no_ads_found(soup)
            return ads
        
        if debug:
            self.log_callback(f"🔗 Total de links de anúncios encontrados para processar: {len(found_links)}")
        
        positive_matches_count = 0
        negative_matches_count = 0
        not_valid_or_invalid_count = 0
        
        for i, link in enumerate(found_links):
            if debug:
                self.log_callback(f"--- Processando link {i+1}/{len(found_links)} ---")
            
            ad_url, ad_title = self._extract_ad_details(link, debug)
            
            if not ad_url or not ad_title:
                self._handle_invalid_ad(link, ad_url, ad_title)
                not_valid_or_invalid_count += 1
                continue
            
            self._log_found_ad_to_file(page_url, ad_title, ad_url)
            
            match_positive, match_negative = self._check_keyword_matches(
                ad_title, keywords, negative_keywords_list, debug)
            
            positive_matches_count += 1 if match_positive else 0
            negative_matches_count += 1 if match_negative else 0
            
            if match_positive and not match_negative:
                full_url = urljoin(self.base_url, ad_url)
                ads.append({"title": ad_title, "url": full_url})
                if debug:
                    self.log_callback(f"➡️ Anúncio VÁLIDO adicionado: '{ad_title}'")
            else:
                not_valid_or_invalid_count += 1
                if debug:
                    self.log_callback("🚫 Anúncio IGNORADO (não atendeu aos critérios de correspondência positiva e/ou negativa).")
        
        self._log_extraction_summary(
            len(ads), positive_matches_count, negative_matches_count, not_valid_or_invalid_count)
        
        return ads

    def _log_debug_info(self, soup, keywords, negative_keywords_list, page_url):
        self.log_callback(f"🔍 Iniciando extração de anúncios da página: {page_url}")
        self.log_callback(f"📌 Palavras-chave positivas: {keywords}")
        self.log_callback(f"📌 Palavras-chave negativas: {negative_keywords_list or 'Nenhuma'}")
        self.log_callback(f"📄 Tamanho do HTML: {len(str(soup))} caracteres")

    def _find_ad_links(self, soup, debug=False):
        selectors = [
            "a[data-testid='ad-card-link']",
            "a.fnmrjs-0",
            "a[href*='/v-']",
            "a.olx-ad-card__link-wrapper",
            "a.olx-adcard__link"
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                if debug:
                    self.log_callback(f"🔍 Usando seletor: {selector} ({len(links)} links)")
                return links
        
        return []

    def _handle_no_ads_found(self, soup):
        self.log_callback("⚠️ Nenhum link de anúncio encontrado com os seletores conhecidos")
        with open("debug_no_ads.html", "w", encoding="utf-8") as f:
            f.write(str(soup))

    def _extract_ad_details(self, link, debug=False):
        ad_url = link.get("href")
        ad_title = (
            link.get("title") or 
            link.get("aria-label") or 
            (link.find("h2") and link.find("h2").get_text(strip=True)) or
            (link.find("span") and link.find("span").get_text(strip=True)) or
            ""
        ).lower()
        
        if debug:
            self.log_callback(f"URL do anúncio: {ad_url}")
            self.log_callback(f"Título do anúncio (processado): '{ad_title}'")
        
        return ad_url, ad_title

    def _handle_invalid_ad(self, link, ad_url, ad_title):
        if not ad_url:
            self.log_callback(f"⚠️ Link sem URL: {link.prettify().strip()}")
        if not ad_title:
            self.log_callback(f"⚠️ Link sem título detectável: {link.prettify().strip()}")

    def _check_keyword_matches(self, ad_title, keywords, negative_keywords_list, debug=False):
        match_positive = any(keyword.lower() in ad_title for keyword in keywords)
        match_negative = any(negative.lower() in ad_title for negative in negative_keywords_list or [])
        
        if debug:
            if match_positive:
                self.log_callback(f"✅ Título '{ad_title}' CORRESPONDE a uma palavra-chave POSITIVA.")
            else:
                self.log_callback(f"❌ Título '{ad_title}' NÃO CORRESPONDE a nenhuma palavra-chave POSITIVA.")
            
            if match_negative:
                self.log_callback(f"❌ Título '{ad_title}' CORRESPONDE a uma palavra-chave NEGATIVA.")
            else:
                self.log_callback(f"✅ Título '{ad_title}' NÃO CORRESPONDE a nenhuma palavra-chave NEGATIVA.")
        
        return match_positive, match_negative

    def _log_extraction_summary(self, valid_ads_count, positive_matches, negative_matches, invalid_count):
        self.log_callback(f"📊 Resumo da extração: {valid_ads_count} anúncios válidos encontrados.")
        self.log_callback(f"👍 Total de títulos com palavras-chave positivas: {positive_matches}")
        self.log_callback(f"👎 Total de títulos com palavras-chave negativas: {negative_matches}")
        self.log_callback(f"🚫 Total de anúncios não válidos ou inválidos: {invalid_count}")