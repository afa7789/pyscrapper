import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import cloudscraper
from fake_useragent import UserAgent
import json

class MarketRoxoScraperCloudflare:
    def __init__(self, log_callback, base_url, proxies=""):
        """Initializes the scraper with the base URL and headers."""
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        
        self.base_url = base_url
        self.log_callback = log_callback
        # self.proxies = self._setup_proxies(proxies)
        
        # Inicializa o cloudscraper que bypassa Cloudflare automaticamente
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # Setup de User Agents rotativos
        self.ua = UserAgent()
        self._setup_headers()
        
        # Delay entre requests para parecer mais humano
        self.delay_min = 15
        self.delay_max = 35
        
        self.log_callback(f"🔍 MarketRoxoScraper inicializado com bypass Cloudflare")

    # def _setup_proxies(self, proxies):
    #     """Configura proxies se fornecidos"""
    #     if proxies and proxies != "":
    #         if isinstance(proxies, str):
    #             # Assume formato "user:pass@ip:port" ou "ip:port"
    #             if '@' in proxies:
    #                 auth, server = proxies.split('@')
    #                 username, password = auth.split(':')
    #                 ip, port = server.split(':')
    #                 return {
    #                     'http': f'http://{username}:{password}@{ip}:{port}',
    #                     'https': f'http://{username}:{password}@{ip}:{port}'
    #                 }
    #             else:
    #                 ip, port = proxies.split(':')
    #                 return {
    #                     'http': f'http://{ip}:{port}',
    #                     'https': f'http://{ip}:{port}'
    #                 }
    #         return proxies
    #     return None

    def _setup_headers(self):
        """Configura headers realistas para evitar detecção"""
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
        """Gera headers aleatórios para cada request"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = self.ua.random
        
        # Adiciona alguns headers extras aleatoriamente
        if random.choice([True, False]):
            headers['X-Forwarded-For'] = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        
        return headers

    def _build_query(self, keywords):
        """Builds a clean query string from keywords, splitting on spaces and removing duplicates."""
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = " ".join(unique_keywords)
        return query

    def _random_delay(self):
        """Delay aleatório entre requests"""
        delay = random.uniform(self.delay_min, self.delay_max)
        self.log_callback(f"⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _make_request(self, url, max_retries=3):
        """Faz request com retry e bypass Cloudflare"""
        for attempt in range(max_retries):
            try:
                headers = self._get_random_headers()
                
                # Configura o scraper com novos headers
                self.scraper.headers.update(headers)
                
                # # Usa proxy se disponível
                # if self.proxies:
                #     response = self.scraper.get(url, proxies=self.proxies, timeout=30)
                # else:
                    # response = self.scraper.get(url, timeout=30)
                response = self.scraper.get(url, timeout=30)
                
                response.raise_for_status()
                
                # Verifica se não foi bloqueado pelo Cloudflare
                if "cloudflare" in response.text.lower() and "blocked" in response.text.lower():
                    raise Exception("Bloqueado pelo Cloudflare")
                
                self.log_callback(f"✅ Request bem-sucedido: {response.status_code}")
                return response
                
            except Exception as e:
                self.log_callback(f"❌ Tentativa {attempt + 1} falhou: {str(e)}")
                if attempt < max_retries - 1:
                    # Delay maior entre tentativas
                    time.sleep(random.uniform(30, 60))
                    
                    # Recria o scraper para nova sessão
                    self.scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': random.choice(['chrome', 'firefox']),
                            'platform': random.choice(['windows', 'linux', 'darwin']),
                            'desktop': True
                        }
                    )
                else:
                    raise e

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
        """Searches for ads across multiple MarketRoxo pages."""
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
                
                # Verifica se chegou ao fim
                if "Nenhum anúncio foi encontrado" in soup.text or "Não encontramos nenhum resultado" in soup.text:
                    self.log_callback("🔚 Fim das páginas disponíveis.")
                    break
                
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list)
                
                if new_ads:
                    self.log_callback(f"✅ Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.log_callback(f"⚠️ Nenhum anúncio relevante na página {page}.")
                
                page += 1
                
                # Delay antes da próxima página
                if page <= max_pages:
                    self._random_delay()
                
            except Exception as e:
                self.log_callback(f"💥 Erro na página {page}: {e}")
                break
        
        self.log_callback(f"🎯 Total de anúncios encontrados: {len(ads)}")
        return ads

    def _extract_ads_tested(self, filename, keywords, negative_keywords_list=None):
        """Extracts ads from an HTML file by parsing its soup."""
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
        soup = BeautifulSoup(content, "html.parser")
        return self._extract_ads(soup, keywords, negative_keywords_list)

    def _extract_ads(self, soup, keywords, negative_keywords_list=None, page_url=""):
        """
        Extracts ads from an HTML page.
        Args:
            soup (BeautifulSoup): The BeautifulSoup object of the page.
            keywords (list): List of positive keywords.
            negative_keywords_list (list, optional): List of negative keywords. Defaults to None.
            page_url (str, optional): The URL of the page being scraped. Defaults to "".
        """
        # in case I want to change this function to reduce number of logs
        log_cb = self.log_callback
        ads = []
        
        # Initialize counters for logging
        positive_matches_count = 0
        negative_matches_count = 0

        # Log keywords being used
        log_cb(f"🔑 Palavras-chave positivas sendo usadas: {keywords}")
        log_cb(f"🚫 Palavras-chave negativas sendo usadas: {negative_keywords_list}")
        log_cb(f"🌐 URL da página sendo processada: {page_url}")
        
        # Tenta diferentes seletores do OLX
        selectors = [
            "a[data-testid='ad-card-link']",  # Novo seletor OLX
            "a.fnmrjs-0",  # Outro seletor possível
            "a[href*='/v-']",  # Links de anúncios
            "a.olx-ad-card__link-wrapper",  # Seletor alternativo
            "a.olx-adcard__link"  # Seletor original
        ]
        
        found_links = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                found_links = links
                log_cb(f"🔍 Usando seletor: {selector} ({len(links)} links)")
                break
        
        if not found_links:
            log_cb("⚠️ Nenhum link de anúncio encontrado com os seletores conhecidos")
            # Debug: salva a página para análise
            with open("debug_no_ads.html", "w", encoding="utf-8") as f:
                f.write(str(soup))
            return ads
        
        log_cb(f"🔗 Total de links de anúncios encontrados para processar: {len(found_links)}")

        for i, link in enumerate(found_links):
            ad_url = link.get("href")
            
            # Tenta diferentes formas de obter o título
            ad_title = (
                link.get("title") or 
                link.get("aria-label") or 
                (link.find("h2") and link.find("h2").get_text(strip=True)) or
                (link.find("span") and link.find("span").get_text(strip=True)) or
                ""
            ).lower()
            
            has_ad_url = bool(ad_url)
            has_ad_title = bool(ad_title)
            
            log_cb(f"--- Processando link {i+1}/{len(found_links)} ---")
            log_cb(f"URL do anúncio: {ad_url}")
            log_cb(f"Título do anúncio (processado): '{ad_title}'")

            if has_ad_url and has_ad_title:
                match_positive = any(keyword.lower() in ad_title for keyword in keywords)
                match_negative = any(negative.lower() in ad_title for negative in negative_keywords_list or [])
                
                # Increment counters based on matches
                if match_positive:
                    positive_matches_count += 1
                    log_cb(f"✅ Título '{ad_title}' CORRESPONDE a uma palavra-chave POSITIVA.")
                else:
                    log_cb(f"❌ Título '{ad_title}' NÃO CORRESPONDE a nenhuma palavra-chave POSITIVA.")
                
                if match_negative:
                    negative_matches_count += 1
                    log_cb(f"❌ Título '{ad_title}' CORRESPONDE a uma palavra-chave NEGATIVA.")
                else:
                    log_cb(f"✅ Título '{ad_title}' NÃO CORRESPONDE a nenhuma palavra-chave NEGATIVA.")


                if match_positive and not match_negative:
                    full_url = urljoin(self.base_url, ad_url)
                    ads.append({"title": ad_title, "url": full_url})
                    log_cb(f"➡️ Anúncio VÁLIDO adicionado: '{ad_title}'")
                    # Log to secondary file
                    self._log_found_ad_to_file(page_url, ad_title, full_url)
                else:
                    log_cb(f"🚫 Anúncio IGNORADO (não atendeu aos critérios de correspondência positiva e/ou negativa).")
            else:
                if not has_ad_url:
                    log_cb(f"⚠️ Link sem URL: {link.prettify().strip()}")
                if not has_ad_title:
                    log_cb(f"⚠️ Link sem título detectável: {link.prettify().strip()}")
            log_cb(f"---------------------------------------------")


        # Log the final counts
        log_cb(f"📊 Resumo da extração: {len(ads)} anúncios válidos encontrados.")
        log_cb(f"👍 Total de títulos com palavras-chave positivas: {positive_matches_count}")
        log_cb(f"👎 Total de títulos com palavras-chave negativas: {negative_matches_count}")
        
        return ads

    def _non_extracted_ads_tested(self, filename, keywords, negative_keywords_list=None):
        """Extracts ads that do not match the keywords from an HTML file."""
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
        soup = BeautifulSoup(content, "html.parser")
        return self._non_extracted_ads(soup, keywords, negative_keywords_list)

    def _non_extracted_ads(self, soup, keywords, negative_keywords_list=None):
        _non_extracted_ads = []
        
        # Usa os mesmos seletores da função _extract_ads
        selectors = [
            "a[data-testid='ad-card-link']",
            "a.fnmrjs-0",
            "a[href*='/v-']",
            "a.olx-ad-card__link-wrapper",
            "a.olx-adcard__link"
        ]
        
        found_links = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                found_links = links
                break
        
        for link in found_links:
            ad_url = link.get("href")
            ad_title = (
                link.get("title") or 
                link.get("aria-label") or 
                (link.find("h2") and link.find("h2").get_text(strip=True)) or
                (link.find("span") and link.find("span").get_text(strip=True)) or
                ""
            ).lower()
            
            if ad_url and ad_title and (
                not any(keyword.lower() in ad_title for keyword in keywords)
                or any(negative.lower() in ad_title for negative in negative_keywords_list or [])
            ):
                full_url = urljoin(self.base_url, ad_url)
                _non_extracted_ads.append({"title": ad_title, "url": full_url})
        
        return _non_extracted_ads