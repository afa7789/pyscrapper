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
        self._setup_headers()
        
        # Delay entre requests para parecer mais humano
        self.delay_min = 15
        self.delay_max = 35
        
        self.log_callback(f"🔍 MarketRoxoScraper inicializado com bypass Cloudflare")

    def _setup_proxies(self, proxies):
        """Configura proxies se fornecidos"""
        # if proxies and proxies != "":
        #     if isinstance(proxies, str):
        #         # Assume formato "user:pass@ip:port" ou "ip:port"
        #         if '@' in proxies:
        #             auth, server = proxies.split('@')
        #             username, password = auth.split(':')
        #             ip, port = server.split(':')
        #             return {
        #                 'http': f'http://{username}:{password}@{ip}:{port}',
        #                 'https': f'http://{username}:{password}@{ip}:{port}'
        #             }
        #         else:
        #             ip, port = proxies.split(':')
        #             return {
        #                 'http': f'http://{ip}:{port}',
        #                 'https': f'http://{ip}:{port}'
        #             }
            # return proxies
        return None

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
        query = "+".join(unique_keywords)
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
                    time.sleep(random.uniform(10, 60))
                    
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
                    self.log_callback(f"🔚 Páginade anúncios não encotrados. url:{url}")
                    # self.log_callback("🔚 Fim das páginas disponíveis.")
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

    def scrape_err(self, keywords, negative_keywords_list=None, max_pages=1, save_page=False):
        # ... (seu código existente) ...

        collected_ads = []
        parsed_urls = set() # Para evitar reprocessar a mesma URL em caso de redirecionamento ou loop
        
        # Gera a string de keywords para a URL
        search_query = "+".join(keywords)
        self.log_callback(f"🚀 Iniciando scraping para: {search_query}")

        for page_num in range(1, max_pages + 1):
            url = f"{self.base_url}/brasil?q={search_query}"
            if page_num > 1:
                url += f"&o={page_num}"
            
            self.log_callback(f"📄 Scraping página {page_num}... {url}")
            
            if url in parsed_urls:
                self.log_callback(f"⚠️ URL já processada, pulando: {url}")
                break
            parsed_urls.add(url)

            try:
                # Usa o cloudscraper para fazer a requisição
                response = self.scraper.get(url, proxies=self.proxies)
                response.raise_for_status()  # Levanta HTTPError para 4XX/5XX
                self.log_callback(f"✅ Request bem-sucedido: {response.status_code}")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # --- INÍCIO DA MODIFICAÇÃO PARA DEBUG ---
                # Aumenta a granularidade do log para ver o que está sendo extraído
                found_ads_on_page = []
                for ad_div in soup.select('ul.sc-1fcmfeb-0.kpMXuJ > li'): # Seletor principal para anúncios
                    try:
                        title_tag = ad_div.select_one('h2.sc-1fcmfeb-0.dkQhY') # Seletor de título
                        url_tag = ad_div.select_one('a.sc-1fcmfeb-0.chDgpK') # Seletor de URL

                        if title_tag and url_tag:
                            title = title_tag.text.strip()
                            ad_url = urljoin(self.base_url, url_tag['href'])
                            
                            # Verifica palavras-chave positivas e negativas
                            match_positive, match_negative = self._check_keyword_matches(
                                title, keywords, negative_keywords_list
                            )

                            if match_positive and not match_negative:
                                found_ads_on_page.append({"title": title, "url": ad_url})
                                # self.log_callback(f"✅ Anúncio válido encontrado: {title}") # Log granular
                            # else:
                                # self.log_callback(f"❌ Anúncio descartado (filtro): {title}") # Log granular
                    except Exception as e:
                        # self.log_callback(f"⚠️ Erro ao processar div de anúncio: {e}") # Log granular
                        pass # Ignora divs mal-formadas
                # --- FIM DA MODIFICAÇÃO PARA DEBUG ---

                if not found_ads_on_page:
                    # Se não encontrou anúncios após a tentativa de extração
                    # Salva o HTML para depuração
                    if save_page:
                        debug_filename = f"debug_failed_scrape_{time.time()}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        self.log_callback(f"🔚 Página sem anúncios encontrados. HTML salvo em: {debug_filename}. URL: {url}")
                    raise ValueError(f"No ads found on page - interpreted as page failure.")
                
                # Se encontrou anúncios, adiciona à lista
                collected_ads.extend(found_ads_on_page)
                self.log_callback(f"✅ Encontrados {len(found_ads_on_page)} anúncios na página {page_num}.")

                if page_num < max_pages:
                    self.log_callback(f"⏳ Aguardando {self.delay_min}-{self.delay_max}s...")
                    time.sleep(random.uniform(self.delay_min, self.delay_max))
                
            except requests.exceptions.HTTPError as http_err:
                self.log_callback(f"💥 Erro HTTP: {http_err} para URL: {url}")
                # Salva o HTML em caso de erro HTTP também
                if save_page:
                    debug_filename = f"debug_http_error_{http_err.response.status_code}_{time.time()}.html"
                    with open(debug_filename, "w", encoding="utf-8") as f:
                        f.write(http_err.response.text)
                raise http_err # Re-lança para ser pego pelo chamador

            except Exception as e:
                self.log_callback(f"💥 Erro durante a requisição ou processamento: {e} para URL: {url}")
                # Salva o HTML em caso de erro geral
                if 'response' in locals() and response:
                    if save_page:
                        debug_filename = f"debug_general_error_{time.time()}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        self.log_callback(f"HTML salvo em: {debug_filename}")
                raise e # Re-lança para ser pego pelo chamador
        
        self.log_callback(f"🎯 Total de anúncios encontrados: {len(collected_ads)}")
        return collected_ads


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

    def _log_debug_info(self, soup, keywords, negative_keywords_list, page_url):
        """Log debug information about the extraction process"""
        self.log_callback(f"🔍 Iniciando extração de anúncios da página: {page_url}")
        self.log_callback(f"📌 Palavras-chave positivas: {keywords}")
        self.log_callback(f"📌 Palavras-chave negativas: {negative_keywords_list or 'Nenhuma'}")
        self.log_callback(f"📄 Tamanho do HTML: {len(str(soup))} caracteres")

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

    def _check_keyword_matches(self, ad_title, keywords, negative_keywords_list, debug=False):
        """Check for positive and negative keyword matches"""
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
        """Log summary of the extraction process"""
        self.log_callback(f"📊 Resumo da extração: {valid_ads_count} anúncios válidos encontrados.")
        self.log_callback(f"👍 Total de títulos com palavras-chave positivas: {positive_matches}")
        self.log_callback(f"👎 Total de títulos com palavras-chave negativas: {negative_matches}")
        self.log_callback(f"🚫 Total de anúncios não válidos ou inválidos: {invalid_count}")