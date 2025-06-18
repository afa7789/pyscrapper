import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import cloudscraper
from fake_useragent import UserAgent
import json
from itertools import permutations

class MarketRoxoScraperCloudflare:
    def __init__(self, log_callback, base_url, proxies=""):
        """Initializes the scraper with the base URL and headers."""
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        
        self.base_url = base_url
        self.log_callback = log_callback
        self.proxies = self._setup_proxies(proxies)
        
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
        # Ensure initial headers are set up for the scraper instance
        self._setup_headers() 
        
        # Delay entre requests para parecer mais humano
        self.delay_min = 15
        self.delay_max = 35
        
        self.log_callback(f"🔍 MarketRoxoScraper inicializado com bypass Cloudflare")

    def _setup_proxies(self, proxies):
        """Configura proxies se fornecidos"""
        if proxies and proxies != "":
            if isinstance(proxies, str):
                # Assume formato "user:pass@ip:port" ou "ip:port"
                # Simplesmente retorna o dicionário esperado por requests
                proxy_config = {
                    "http": f"{proxies}",
                    "https": f"{proxies}"
                }
                self.log_callback(f"✅ Proxies configurados: {proxy_config}")
                return proxy_config
            else:
                self.log_callback("⚠️ Formato de proxy inválido. Use uma string como 'user:pass@ip:port'.")
                return None
        self.log_callback("ℹ️ Nenhum proxy configurado.")
        return None

    def _setup_headers(self):
        """Configura cabeçalhos com um User-Agent aleatório e define base_headers."""
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
        self.headers = self._get_random_headers() # Set initial headers for the scraper
        self.scraper.headers.update(self.headers) # Update scraper with these headers
        self.log_callback(f"👤 User-Agent inicializado: {self.headers['User-Agent']}")

    def _get_random_headers(self):
        """Gera headers aleatórios para cada request."""
        headers = self.base_headers.copy()
        headers['User-Agent'] = self.ua.random
        
        # Adiciona alguns headers extras aleatoriamente
        if random.choice([True, False]):
            headers['X-Forwarded-For'] = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        
        return headers

    def _build_query(self, keywords):
        """Builds a clean query string from keywords, splitting on spaces and removing duplicates."""
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = "+".join(unique_keywords)
        return query

    def _random_delay(self):
        """Delay aleatório entre requests."""
        delay = random.uniform(self.delay_min, self.delay_max)
        self.log_callback(f"⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _make_request(self, url, max_retries=3):
        """Faz request com retry e bypass Cloudflare."""
        for attempt in range(max_retries):
            try:
                headers = self._get_random_headers()
                
                # Configura o scraper com novos headers
                self.scraper.headers.update(headers)
                
                response = self.scraper.get(url, proxies=self.proxies, timeout=30)
                
                response.raise_for_status()
                
                # Verifica se não foi bloqueado pelo Cloudflare
                # Note: Cloudscraper handles this usually, but an explicit check can be a fallback.
                if "cloudflare" in response.text.lower() and "blocked" in response.text.lower():
                    raise Exception("Bloqueado pelo Cloudflare")
                
                self.log_callback(f"✅ Request bem-sucedido: {response.status_code}")
                # _random_delay is called by the main scrape method after processing the page
                return response
                
            except Exception as e:
                self.log_callback(f"❌ Tentativa {attempt + 1} falhou para {url}: {str(e)}")
                if attempt < max_retries - 1:
                    # Delay maior entre tentativas
                    time.sleep(random.uniform(10, 60))
                    
                    # Recria o scraper para nova sessão, com novo browser config
                    self.scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': random.choice(['chrome', 'firefox']),
                            'platform': random.choice(['windows', 'linux', 'darwin']),
                            'desktop': True
                        }
                    )
                    self._setup_headers() # Re-setup headers for the new scraper instance
                else:
                    self.log_callback(f"⚠️ Todas as {max_retries} tentativas falharam para {url}.")
                    return None # Return None if all retries fail

    def _log_extraction_summary(self, valid_ads_count, positive_matches, negative_matches, invalid_count):
        """Log summary of the extraction process"""
        self.log_callback(f"📊 Resumo da extração: {valid_ads_count} anúncios válidos encontrados.")
        self.log_callback(f"👍 Total de títulos com palavras-chave positivas: {positive_matches}")
        self.log_callback(f"👎 Total de títulos com palavras-chave negativas: {negative_matches}")
        self.log_callback(f"🚫 Total de títulos não correspondentes (positivas): {invalid_count}")

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
                if response is None: # _make_request already handles retries, if it's None, it means all failed
                    self.log_callback(f"🛑 Não foi possível obter resposta para a página {page}. Abortando.")
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                
                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                    self.log_callback(f"💾 Página {page} salva.")
                
                # Verifica se chegou ao fim
                # You might need to refine this check based on actual "no results" page content
                if "Nenhum anúncio foi encontrado" in soup.text or "Não encontramos nenhum resultado" in soup.text:
                    self.log_callback(f"🔚 Página de anúncios não encontrados. URL: {url}")
                    break
                
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list, page_url=url) # Pass page_url
                
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
                # You might want to decide if a single page error should stop the whole process
                break
        
        self.log_callback(f"🎯 Total de anúncios encontrados: {len(ads)}")
        return ads

    def _extract_ads(self, soup, keywords, negative_keywords_list=None, page_url=""):
        """
        Extracts ads from an HTML page.
        Args:
            soup (BeautifulSoup): The BeautifulSoup object of the page.
            keywords (list): List of positive keywords.
            negative_keywords_list (list, optional): List of negative keywords. Defaults to None.
            page_url (str, optional): The URL of the page being scraped. Defaults to "".
        Returns:
            list: List of valid ads found
        """
        debug = False  # Set this to False to disable debug logging
        ads = []
        
        if debug:
            self._log_debug_info(soup, keywords, negative_keywords_list, page_url)
        
        found_links = self._find_ad_links(soup, debug)
        if not found_links:
            self._handle_no_ads_found(soup)
            return ads
        
        if debug:
            self.log_callback(f"🔗 Total de links de anúncios encontrados para processar: {len(found_links)}")
        
        # Initialize counters for logging
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
            
            # self._log_found_ad_to_file(page_url, ad_title, ad_url)
            
            match_positive, match_negative = self._check_keyword_matches(
                ad_title, 
                keywords, 
                negative_keywords_list,
                debug
            )
            
            # Update counters
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
            len(ads),
            positive_matches_count,
            negative_matches_count,
            not_valid_or_invalid_count
        )
        
        return ads

    def _check_keyword_matches(self, ad_title, keywords, negative_keywords_list, debug=False):
        """Check for positive and negative keyword matches"""
        ad_title_lower = ad_title.lower()
        match_positive = any(keyword.lower() in ad_title_lower for keyword in keywords)
        match_negative = any(negative.lower() in ad_title_lower for negative in negative_keywords_list or [])
        
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

    def _find_ad_links(self, soup, debug=False):
        """Find ad links in the page using multiple possible selectors"""
        selectors = [
            "a[data-testid='ad-card-link']",  # Novo seletor OLX
            "a.fnmrjs-0",  # Outro seletor possível
            "a[href*='/v-']",  # Links de anúncios
            "a.olx-ad-card__link-wrapper",  # Seletor alternativo
            "a.olx-adcard__link"  # Seletor original
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                if debug:
                    self.log_callback(f"🔍 Usando seletor: {selector} ({len(links)} links)")
                return links
        
        return []

    def _handle_no_ads_found(self, soup):
        """Handle case when no ads are found"""
        self.log_callback("⚠️ Nenhum link de anúncio encontrado com os seletores conhecidos")
        # Debug: save the page for analysis
        with open("debug_no_ads.html", "w", encoding="utf-8") as f:
            f.write(str(soup))

    def _extract_ad_details(self, link, debug=False):
        """Extract URL and title from an ad link"""
        ad_url = link.get("href")
        
        # Try different ways to get the title
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
        """Handle invalid ads (missing URL or title)"""
        if not ad_url:
            self.log_callback(f"⚠️ Link sem URL: {link.prettify().strip()}")
        if not ad_title:
            self.log_callback(f"⚠️ Link sem título detectável: {link.prettify().strip()}")

    def _log_debug_info(self, soup, keywords, negative_keywords_list, page_url):
        """Log debug information about the extraction process"""
        self.log_callback(f"🔍 Iniciando extração de anúncios da página: {page_url}")
        self.log_callback(f"📌 Palavras-chave positivas: {keywords}")
        self.log_callback(f"📌 Palavras-chave negativas: {negative_keywords_list or 'Nenhuma'}")
        self.log_callback(f"📄 Tamanho do HTML: {len(str(soup))} caracteres")

    def _log_found_ad_to_file(self, page_url, ad_title, ad_url):
        """Logs found ads to a secondary file."""
        try:
            with open("found_ads.log", "a", encoding="utf-8") as f:
                f.write(f"Página: {page_url}\n")
                f.write(f"Título do Anúncio: {ad_title}\n")
                f.write(f"Link do Anúncio: {ad_url}\n")
                f.write("-" * 50 + "\n") # Separator for readability
        except Exception as e:
            self.log_callback(f"❌ Erro ao escrever no arquivo found_ads.log: {e}")

    def scrape_err(self, keywords, negative_keywords_list=None, query_keywords=None ,  max_pages=1, save_page=False):
        """
        Searches for ads across multiple MarketRoxo pages using existing robust methods.
        This version is designed to specifically highlight scraping failures by raising exceptions.
        It uses 'query_keywords' for the search URL and 'keywords' for ad filtering.
        """
        # Use query_keywords to build the search query for the URL
        search_query = self._build_query(query_keywords)
        collected_ads = []

        if query_keywords is None:
            query_keywords = keywords
        
        self.log_callback(f"🚀 Iniciando scraping para: {search_query} (query keywords)")

        for page_num in range(1, max_pages + 1):
            url = f"{self.base_url}/brasil?q={search_query}"
            if page_num > 1:
                url += f"&o={page_num}"
            
            self.log_callback(f"📄 Scraping página {page_num}... {url}")
            
            try:
                response = self._make_request(url)
                
                # If _make_request failed after retries, it returns None.
                # In scrape_err, we want to explicitly raise an error in such cases.
                if response is None:
                    self.log_callback(f"🛑 Não foi possível obter resposta para a página {page_num}. Falha crítica.")
                    raise ConnectionError(f"Failed to retrieve page content after multiple retries for URL: {url}")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                if save_page:
                    debug_filename = f"debug_page_{page_num}.html"
                    with open(debug_filename, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    self.log_callback(f"💾 Página {page_num} salva para depuração: {debug_filename}.")
                
                # Check for "no ads found" message to gracefully end or indicate a specific condition
                if "Nenhum anúncio foi encontrado" in soup.text or "Não encontramos nenhum resultado" in soup.text:
                    self.log_callback(f"🔚 Página {page_num} indica fim dos anúncios ou nenhum resultado. URL: {url}")
                    # If no ads are found on the first page, and that's considered a "scrape failure"
                    # you could add a condition like: `if page_num == 1: raise NoAdsFoundError(...)`
                    break

                # Reuse the _extract_ads method for parsing and filtering
                # Pass 'keywords' and 'negative_keywords_list' for matching checks
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list, page_url=url)
                
                if new_ads:
                    collected_ads.extend(new_ads)
                    self.log_callback(f"✅ Encontrados {len(new_ads)} anúncios na página {page_num}.")
                else:
                    self.log_callback(f"⚠️ Nenhum anúncio relevante encontrado na página {page_num}.")

                # Apply random delay before proceeding to the next page
                if page_num < max_pages:
                    self._random_delay()
                
            except requests.exceptions.HTTPError as http_err:
                self.log_callback(f"💥 Erro HTTP ({http_err.response.status_code}) para URL: {url}. Detalhes: {http_err}")
                if save_page:
                    debug_filename = f"debug_http_error_{http_err.response.status_code}_{time.time()}.html"
                    with open(debug_filename, "w", encoding="utf-8") as f:
                        f.write(http_err.response.text)
                    self.log_callback(f"HTML do erro HTTP salvo em: {debug_filename}.")
                raise http_err # Re-raise the HTTP error
            except Exception as e:
                self.log_callback(f"💥 Erro inesperado durante o scraping da página {page_num} ({url}): {e}")
                if 'response' in locals() and response:
                    if save_page:
                        debug_filename = f"debug_general_error_{time.time()}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        self.log_callback(f"HTML salvo em: {debug_filename}")
                raise e # Re-raise any other unexpected exception

        self.log_callback(f"🎯 Total de anúncios coletados: {len(collected_ads)}")
        return collected_ads
