import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import cloudscraper
from fake_useragent import UserAgent
import json
from itertools import permutations
from logging_config import get_logger

# Custom Exception for when no ads are found
class NoAdsFoundError(Exception):
    """Custom exception raised when no ads are found on the page, especially on the first page."""
    pass

class MarketRoxoScraperCloudflare:
    def __init__(self, base_url, proxies=""):
        """Initializes the scraper with the base URL and headers."""
        self.logger = get_logger()
        self.base_url = base_url
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

        self.logger.info(f"🥸 MarketRoxoScraper inicializado com bypass Cloudflare")

    def _setup_proxies(self, proxies):
        """Configura proxies se fornecidos"""
        if proxies and proxies != "":
            # Assume formato "user:pass@ip:port" ou "ip:port"
            # Simplesmente retorna o dicionário esperado por requests
            proxy_config = {
                "http": f"{proxies.get('http')}",
                "https": f"{proxies.get('https')}"
            }
            self.logger.info(f"✅ Proxies configurados: {proxy_config}")
            return proxy_config
        self.logger.info("ℹ️ Nenhum proxy configurado.")
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
        self.headers = self._get_random_headers()
        # Update scraper with these headers
        self.scraper.headers.update(self.headers)

    def _get_random_headers(self):
        """Gera headers aleatórios para cada request e loga o User-Agent usado."""
        headers = self.base_headers.copy()
        new_user_agent = self.ua.random
        headers['User-Agent'] = new_user_agent

        # Adiciona alguns headers extras aleatoriamente
        if random.choice([True, False]):
            headers['X-Forwarded-For'] = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"

        self.logger.info(f"👤 Usando User-Agent: {new_user_agent}")
        return headers

    def _build_query(self, keywords):
        """Builds a clean query string from keywords, splitting on spaces and removing duplicates."""
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = "+".join(unique_keywords)
        return query

    def _random_delay(self):
        """Delay aleatório entre requests."""
        delay = random.uniform(self.delay_min, self.delay_max)
        self.logger.info(f"⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _make_request(self, url, max_retries=3):
        """Faz request com retry e bypass Cloudflare."""
        for attempt in range(max_retries):
            try:
                headers = self._get_random_headers()
                self.scraper.headers.update(headers)

                response = self.scraper.get(url, proxies=self.proxies, timeout=30)
                response.raise_for_status()

                if "cloudflare" in response.text.lower() and "blocked" in response.text.lower():
                    raise Exception("Bloqueado pelo Cloudflare")

                self.logger.info(f"✅ Request bem-sucedido: {response.status_code}")
                return response

            except Exception as e:
                self.logger.error(f"❌ Tentativa {attempt + 1} falhou para {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(10, 60))
                    self.scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': random.choice(['chrome', 'firefox']),
                            'platform': random.choice(['windows', 'linux', 'darwin']),
                            'desktop': True
                        }
                    )
                    self._setup_headers()
                else:
                    self.logger.warning(f"⚠️ Todas as {max_retries} tentativas falharam para {url}.")
                    return None

    def _log_extraction_summary(self, valid_ads_count, positive_matches, negative_matches, invalid_count):
        """Log summary of the extraction process"""
        self.logger.info(f"📊 Resumo da extração: {valid_ads_count} anúncios válidos encontrados.")
        self.logger.info(f"👍 Total de títulos com palavras-chave positivas: {positive_matches}")
        self.logger.info(f"👎 Total de títulos com palavras-chave negativas: {negative_matches}")
        self.logger.info(f"🚫 Total de títulos não correspondentes (positivas): {invalid_count}")

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
        """Searches for ads across multiple MarketRoxo pages."""
        query = self._build_query(keywords)
        ads = []
        page = 1

        self.logger.info(f"🚀 Iniciando scraping para: {query}")

        while page <= max_pages:
            url = f"{self.base_url}/brasil?q={query}&o={page}" if page > 1 else f"{self.base_url}/brasil?q={query}"
            self.logger.info(f"📄 Scraping página {page}... {url}")

            try:
                response = self._make_request(url)
                if response is None:
                    self.logger.error(f"🛑 Não foi possível obter resposta para a página {page}. Abortando.")
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                    self.logger.info(f"💾 Página {page} salva.")

                if "Nenhum anúncio foi encontrado" in soup.text or "Não encontramos nenhum resultado" in soup.text:
                    self.logger.info(f"🔚 Página de anúncios não encontrados. URL: {url}")
                    break

                new_ads = self._extract_ads(soup, keywords, negative_keywords_list, page_url=url)

                if new_ads:
                    self.logger.info(f"✅ Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                else:
                    self.logger.info(f"⚠️ Nenhum anúncio relevante na página {page}.")

                page += 1

                if page <= max_pages:
                    self._random_delay()

            except Exception as e:
                self.logger.error(f"💥 Erro na página {page}: {e}")
                break

        self.logger.info(f"🎯 Total de anúncios encontrados: {len(ads)}")
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
        debug = False
        ads = []

        if debug:
            self._log_debug_info(soup, keywords, negative_keywords_list, page_url)

        found_links = self._find_ad_links(soup, debug)
        if not found_links:
            self._handle_no_ads_found(soup)
            return ads

        if debug:
            self.logger.info(f"🔗 Total de links de anúncios encontrados para processar: {len(found_links)}")

        positive_matches_count = 0
        negative_matches_count = 0
        not_valid_or_invalid_count = 0

        for i, link in enumerate(found_links):
            if debug:
                self.logger.info(f"--- Processando link {i+1}/{len(found_links)} ---")

            ad_url, ad_title, ad_price = self._extract_ad_details(link, debug)

            if not ad_url or not ad_title:
                self._handle_invalid_ad(link, ad_url, ad_title)
                not_valid_or_invalid_count += 1
                continue

            match_positive, match_negative = self._check_keyword_matches(
                ad_title, keywords, negative_keywords_list, debug
            )

            positive_matches_count += 1 if match_positive else 0
            negative_matches_count += 1 if match_negative else 0

            if match_positive and not match_negative:
                full_url = urljoin(self.base_url, ad_url)
                ads.append({"title": ad_title, "url": full_url, "price": ad_price})
                if debug:
                    self.logger.info(f"➡️ Anúncio VÁLIDO adicionado: '{ad_title}' - Preço: '{ad_price}'")
            else:
                not_valid_or_invalid_count += 1
                if debug:
                    self.logger.info("🚫 Anúncio IGNORADO (não atendeu aos critérios de correspondência positiva e/ou negativa).")

        self._log_extraction_summary(
            len(ads), positive_matches_count, negative_matches_count, not_valid_or_invalid_count
        )

        return ads

    def _check_keyword_matches(self, ad_title, keywords, negative_keywords_list, debug=False):
        """Check for positive and negative keyword matches"""
        ad_title_lower = ad_title.lower()
        match_positive = any(keyword.lower() in ad_title_lower for keyword in keywords)
        match_negative = any(negative.lower() in ad_title_lower for negative in negative_keywords_list or [])

        if debug:
            if match_positive:
                self.logger.info(f"✅ Título '{ad_title}' CORRESPONDE a uma palavra-chave POSITIVA.")
            else:
                self.logger.info(f"❌ Título '{ad_title}' NÃO CORRESPONDE a nenhuma palavra-chave POSITIVA.")

            if match_negative:
                self.logger.info(f"❌ Título '{ad_title}' CORRESPONDE a uma palavra-chave NEGATIVA.")
            else:
                self.logger.info(f"✅ Título '{ad_title}' NÃO CORRESPONDE a nenhuma palavra-chave NEGATIVA.")

        return match_positive, match_negative

    def _find_ad_links(self, soup, debug=False):
        """Find ad links in the page using multiple possible selectors"""
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
                    self.logger.info(f"🔍 Usando seletor: {selector} ({len(links)} links)")
                return links

        return []

    def _handle_no_ads_found(self, soup):
        """Handle case when no ads are found"""
        self.logger.warning("⚠️ Nenhum link de anúncio encontrado com os seletores conhecidos")
        with open("debug_no_ads.html", "w", encoding="utf-8") as f:
            f.write(str(soup))

    def _extract_ad_details(self, link, debug=False):
        """Extract URL, title and price from an ad link"""
        ad_url = link.get("href")
        ad_title = (
            link.get("title") or
            link.get("aria-label") or
            (link.find("h2") and link.find("h2").get_text(strip=True)) or
            (link.find("span") and link.find("span").get_text(strip=True)) or
            ""
        ).lower()

        # Extract price from various possible selectors
        ad_price = ""
        price_selectors = [
            ".olx-adcard__price",
            "[data-testid='ad-price']", 
            ".price",
            ".ad-price",
            ".fnmrjs-0.cpointer"
        ]
        
        for selector in price_selectors:
            price_element = link.find(class_=selector.replace(".", "")) if selector.startswith(".") else link.select_one(selector)
            if price_element:
                ad_price = price_element.get_text(strip=True)
                if ad_price:
                    break
        
        # If no price found in the link itself, try to find it in parent containers
        if not ad_price:
            parent = link.parent
            if parent:
                for selector in price_selectors:
                    price_element = parent.find(class_=selector.replace(".", "")) if selector.startswith(".") else parent.select_one(selector)
                    if price_element:
                        ad_price = price_element.get_text(strip=True)
                        if ad_price:
                            break

        if debug:
            self.logger.info(f"URL do anúncio: {ad_url}")
            self.logger.info(f"Título do anúncio (processado): '{ad_title}'")
            self.logger.info(f"Preço do anúncio: '{ad_price}'")

        return ad_url, ad_title, ad_price

    def _handle_invalid_ad(self, link, ad_url, ad_title):
        """Handle invalid ads (missing URL or title)"""
        if not ad_url:
            self.logger.warning(f"⚠️ Link sem URL: {link.prettify().strip()}")
        if not ad_title:
            self.logger.warning(f"⚠️ Link sem título detectável: {link.prettify().strip()}")

    def _log_debug_info(self, soup, keywords, negative_keywords_list, page_url):
        """Log debug information about the extraction process"""
        self.logger.info(f"🔍 Iniciando extração de anúncios da página: {page_url}")
        self.logger.info(f"📌 Palavras-chave positivas: {keywords}")
        self.logger.info(f"📌 Palavras-chave negativas: {negative_keywords_list or 'Nenhuma'}")
        self.logger.info(f"📄 Tamanho do HTML: {len(str(soup))} caracteres")

    def _log_found_ad_to_file(self, page_url, ad_title, ad_url):
        """Logs found ads to a secondary file."""
        try:
            with open("found_ads.log", "a", encoding="utf-8") as f:
                f.write(f"Página: {page_url}\n")
                f.write(f"Título do Anúncio: {ad_title}\n")
                f.write(f"Link do Anúncio: {ad_url}\n")
                f.write("-" * 50 + "\n")
        except Exception as e:
            self.logger.error(f"❌ Erro ao escrever no arquivo found_ads.log: {e}")

    def scrape_err(self, keywords, positive_keywords_list=None ,negative_keywords_list=None, query_keywords=None,
                   start_page=1, num_pages_to_scrape=1, save_page=False,
                   page_retry_attempts=3, page_retry_delay_min=5, page_retry_delay_max=15):
        """
        Searches for ads across MarketRoxo pages, designed to highlight scraping failures by raising exceptions.
        It uses 'query_keywords' for the search URL and 'keywords' for ad filtering.
        This version includes retries for individual page fetches.
        """
        search_query = self._build_query(query_keywords or keywords)
        collected_ads = []

        self.logger.info(f"🚀 Iniciando scrape para: {search_query} (query keywords) a partir da página {start_page} por {num_pages_to_scrape} páginas.")

        for page_offset in range(num_pages_to_scrape):
            page_num = start_page + page_offset
            url = f"{self.base_url}/brasil?q={search_query}"
            if page_num > 1:
                url += f"&o={page_num}"

            self.logger.info(f"📄 Scraping página {page_num}... {url}")

            current_page_success = False
            for attempt in range(page_retry_attempts):
                try:
                    response = self._make_request(url)

                    if response is None:
                        self.logger.error(f"🛑 Tentativa {attempt + 1}/{page_retry_attempts} falhou para obter resposta para a página {page_num}. URL: {url}")
                        if attempt < page_retry_attempts - 1:
                            time.sleep(random.uniform(page_retry_delay_min, page_retry_delay_max))
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')

                    if save_page:
                        debug_filename = f"debug_page_{page_num}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        self.logger.info(f"💾 Página {page_num} salva para depuração: {debug_filename}.")

                    no_ads_message_found = "Nenhum anúncio foi encontrado" in soup.text or "Não encontramos nenhum resultado" in soup.text

                    # append positive keywords to the keywords list if provided
                    if positive_keywords_list:
                        # Ensure keywords is a list before concatenating
                        keywords_list = keywords if isinstance(keywords, list) else [keywords] if keywords else []
                        # Combine and deduplicate
                        keywords = list(set(keywords_list + positive_keywords_list))

                    new_ads = self._extract_ads(soup, keywords, negative_keywords_list, page_url=url)

                    if no_ads_message_found:
                        self.logger.info(f"🔚 Página {page_num} indica fim dos anúncios ou nenhum resultado. URL: {url}")
                        if page_offset == 0:
                            raise NoAdsFoundError(f"No ads found on page {page_num} (explicit message) for query: '{search_query}' at {url}")
                        else:
                            current_page_success = True
                            break

                    if not new_ads and page_offset == 0:
                        self.logger.info(f"No relevant ads extracted on page {page_num} (implicit no results) for query: '{search_query}' at {url}")

                    if new_ads:
                        collected_ads.extend(new_ads)
                        self.logger.info(f"🔎 Encontrados {len(new_ads)} anúncios na página {page_num}.")
                        current_page_success = True
                        break
                    else:
                        self.logger.info(f"⚠️ Nenhum anúncio relevante encontrado na página {page_num}.")
                        current_page_success = True
                        break

                except NoAdsFoundError as e:
                    self.logger.error(f"💥 NoAdsFoundError na página {page_num} (Tentativa {attempt + 1}/{page_retry_attempts}): {e}")
                    if attempt < page_retry_attempts - 1:
                        time.sleep(random.uniform(page_retry_delay_min, page_retry_delay_max))
                    else:
                        raise e
                except requests.exceptions.HTTPError as http_err:
                    self.logger.error(f"💥 Erro HTTP ({http_err.response.status_code}) na página {page_num} (Tentativa {attempt + 1}/{page_retry_attempts}): {http_err}")
                    if save_page:
                        debug_filename = f"debug_http_error_{http_err.response.status_code}_page_{page_num}_{time.time()}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(http_err.response.text)
                        self.logger.info(f"HTML do erro HTTP salvo em: {debug_filename}.")
                    if attempt < page_retry_attempts - 1:
                        time.sleep(random.uniform(page_retry_delay_min, page_retry_delay_max))
                    else:
                        raise http_err
                except Exception as e:
                    self.logger.error(f"💥 Erro inesperado na página {page_num} (Tentativa {attempt + 1}/{page_retry_attempts}): {e}")
                    if 'response' in locals() and response:
                        if save_page:
                            debug_filename = f"debug_general_error_page_{page_num}_{time.time()}.html"
                            with open(debug_filename, "w", encoding="utf-8") as f:
                                f.write(response.text)
                            self.logger.info(f"HTML salvo em: {debug_filename}")
                    if attempt < page_retry_attempts - 1:
                        time.sleep(random.uniform(page_retry_delay_min, page_retry_delay_max))
                    else:
                        raise e

            if not current_page_success:
                self.logger.warning(f"⚠️ Todas as tentativas falharam para a página {page_num}. Prosseguindo para a próxima página ou finalizando.")
                break

            if current_page_success and page_num < (start_page + num_pages_to_scrape - 1):
                self._random_delay()

        self.logger.info(f"🎯 Total de anúncios coletados nesta chamada: {len(collected_ads)}")
        return collected_ads