import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class MarketRoxoScraper:
    def __init__(self, log_callback, base_url, proxies=""):
        """Initializes the scraper with the base URL and headers."""
        if not callable(log_callback):
            raise ValueError(f"log_callback must be callable, got {type(log_callback)}: {log_callback}")
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.103 Safari/537.36"
        }
        self.delay = 25
        self.log_callback = log_callback
        self.proxies = proxies
        self.log_callback(f"🔍 Debug: MarketRoxoScraper initialized with log_callback={log_callback}")

    def _build_query(self, keywords):
        """Builds a clean query string from keywords, splitting on spaces and removing duplicates."""
        unique_keywords = {word.lower() for keyword in keywords for word in keyword.split()}
        query = "+".join(unique_keywords)
        return query

    def scrape(self, keywords, negative_keywords_list, max_pages=5, save_page=False):
        """Searches for ads across multiple MarketRoxo pages."""
        query = self._build_query(keywords)
        ads = []
        page = 1
        while page <= max_pages:
            url = f"{self.base_url}/brasil?q={query}&o={page}" if page > 1 else f"{self.base_url}/brasil?q={query}"
            self.log_callback(f"Scraping página {page}... {url}")
            try:
                if self.proxies and self.proxies != "":
                    response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=20)
                else:
                    response = requests.get(url, headers=self.headers, timeout=20)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                if save_page:
                    with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup))
                        self.log_callback(f"Página {page} processada com sucesso.")
                if "Nenhum anúncio foi encontrado" in soup.text:
                    self.log_callback("Fim das páginas disponíveis.")
                    break
                new_ads = self._extract_ads(soup, keywords, negative_keywords_list)
                if new_ads:
                    self.log_callback(f"Encontrados {len(new_ads)} anúncios na página {page}.")
                    ads.extend(new_ads)
                page += 1
                time.sleep(self.delay)
            except Exception as e:
                self.log_callback(f"Erro na página {page}: {e}")
                break
        return ads

    def _extract_ads_tested(self, filename, keywords, negative_keywords_list=None):
        """Extracts ads from an HTML file by parsing its soup."""
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
        soup = BeautifulSoup(content, "html.parser")
        return self._extract_ads(soup, keywords)

    def _extract_ads(self, soup, keywords, negative_keywords_list=None):
        """Extracts ads from an HTML page."""
        ads = []
        for link in soup.find_all("a", class_="olx-adcard__link"):
            ad_url = link.get("href")
            ad_title = link.get("title", "").lower()
            has_ad_url = bool(ad_url)
            has_ad_title = bool(ad_title)
            match_positive = any(keyword.lower() in ad_title for keyword in keywords)
            match_negative = any(negative.lower() in ad_title for negative in negative_keywords_list or [])
            if has_ad_url and has_ad_title and match_positive and not match_negative:
                full_url = urljoin(self.base_url, ad_url)
                ads.append({"title": ad_title, "url": full_url})
        return ads

    def _non_extracted_ads_tested(self, filename, keywords, negative_keywords_list=None):
        """Extracts ads that do not match the keywords from an HTML file."""
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
        soup = BeautifulSoup(content, "html.parser")
        return self._non_extracted_ads(soup, keywords)

    def _non_extracted_ads(self, soup, keywords, negative_keywords_list=None):
        _non_extracted_ads = []
        for link in soup.find_all("a", class_="olx-adcard__link"):
            ad_url = link.get("href")
            ad_title = link.get("title", "").lower()
            if ad_url and ad_title and (
                not any(keyword.lower() in ad_title for keyword in keywords)
                or any(negative.lower() in ad_title for negative in negative_keywords_list or [])
            ):
                full_url = urljoin(self.base_url, ad_url)
                _non_extracted_ads.append({"title": ad_title, "url": full_url})
        return _non_extracted_ads