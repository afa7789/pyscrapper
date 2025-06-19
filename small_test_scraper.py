#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exemplo de uso do MarketRoxoScraper2 com bypass Cloudflare
"""

from scraper_cloudflare import MarketRoxoScraperCloudflare
import json
import os
from dotenv import load_dotenv
import time  # Ensure time is imported for log_callback


def log_callback(message):
    """Função de callback para logs"""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")


def main():
    # Carrega variáveis de ambiente
    load_dotenv()

    # Configurações através de variáveis de ambiente
    base_url = os.getenv("MAIN_URL_SCRAPE_ROXO", "https://www.olx.com.br")

    # Configuração do proxy (opcional)
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    # proxy_config = http_proxy or https_proxy or ""

    proxy_config = ""

    # Palavras-chave para buscar (também usadas como query_keywords para a URL)
    keywords_str = "iphone,ipad,apple"
    keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]

    keywords_str2 = os.getenv(
        "DEFAULT_KEYWORDS", "bike,indoor,concept2,spinning,bicicleta,schwinn,technogym")
    keywords2 = [kw.strip() for kw in keywords_str2.split(",") if kw.strip()]

    array_of_keywords = [keywords, keywords2]

    # Palavras-chave negativas (para filtrar)
    negative_keywords_str = os.getenv(
        "NEGATIVE_KEYWORDS_LIST", "quebrada,defeito,peças,sucata")
    negative_keywords = [kw.strip()
                         for kw in negative_keywords_str.split(",") if kw.strip()]

    # Número de páginas para buscar
    max_pages = 1

    # Salvar páginas para debug
    save_page = False

    # Inicializa o scraper
    scraper = MarketRoxoScraperCloudflare(
        log_callback=log_callback,
        base_url=base_url,
        proxies=proxy_config
    )

    # def scrape_err(self, keywords, negative_keywords_list=None, query_keywords=None,
    #                start_page=1, num_pages_to_scrape=1, save_page=False,
    #                page_retry_attempts=3, page_retry_delay_min=5, page_retry_delay_max=15):
    # Teste inicial de scrape err c/ marketroxo,
    try:
        print("🎯 Iniciando busca por anúncios...")
        for current_keywords_for_loop in array_of_keywords:  # Renamed loop variable for clarity
            print(
                f"\n🔍 Buscando anúncios com as palavras-chave: {', '.join(current_keywords_for_loop)}")

            ads = scraper.scrape_err(
                query_keywords=current_keywords_for_loop,
                keywords=current_keywords_for_loop,
                negative_keywords_list=negative_keywords,
                start_page=1,
                num_pages_to_scrape=max_pages,
                save_page=save_page,
                page_retry_attempts=10,
                page_retry_delay_min=30,
                page_retry_delay_max=67
            )

            # Exibe resultados
            print(f"\n📊 RESULTADO FINAL:")
            print(f"Total de anúncios encontrados: {len(ads)}")

    except Exception as e:
        print(f"💥 Erro durante o scraping: {e}")
        return False

    return True


if __name__ == "__main__":

    print("🚀 MarketRoxo Scraper com Bypass Cloudflare")
    print("=" * 50)

    success = main()

    if success:
        print("\n✅ Scraping concluído com sucesso!")
    else:
        print("\n❌ Scraping falhou!")
