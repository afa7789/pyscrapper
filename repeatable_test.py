#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para testar a ideia de scraping repetido.
Sempre executa em modo de teste (logs silenciosos).
"""

import os
import time
from dotenv import load_dotenv
from scraper_cloudflare import MarketRoxoScraperCloudflare

# CONSTANTE: altere este valor conforme necessário para definir o número de execuções
NUM_TESTS = 1000

def log_callback(message):
    """Callback de logs"""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def main():
    """
    Executa o scraping repetido para teste.
    Usa callback silencioso e imprime o resultado final dos testes.
    """
    load_dotenv()

    base_url = os.getenv("MAIN_URL_SCRAPE_ROXO", "https://www.olx.com.br")
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    proxy_config = http_proxy or https_proxy or ""

    keywords_str = os.getenv("DEFAULT_KEYWORDS", "bike,indoor,concept2,spinning,bicicleta,schwinn,technogym")
    keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]

    negative_keywords_str = os.getenv("NEGATIVE_KEYWORDS_LIST", "quebrada,defeito,peças,sucata")
    negative_keywords = [kw.strip() for kw in negative_keywords_str.split(",") if kw.strip()]

    max_pages = 2
    save_page = False

    # Sempre utiliza callback silencioso para testes
    effective_callback = lambda msg: None

    success_count = 0
    error_count = 0
    success_ids = []
    error_types_counts = {}  # Dicionário para registrar erro e quantidade

    print("🚀 Iniciando testes repetidos com MarketRoxo Scraper (modo teste)")

    for i in range(NUM_TESTS):
        scraper = MarketRoxoScraperCloudflare(
            log_callback=effective_callback,
            base_url=base_url,
            proxies=proxy_config
        )
        try:
            scraper.scrape(
                keywords=keywords,
                negative_keywords_list=negative_keywords,
                max_pages=max_pages,
                save_page=save_page
            )
            success_count += 1
            success_ids.append(i)
        except Exception as e:
            error_count += 1
            error_type = type(e).__name__
            error_types_counts[error_type] = error_types_counts.get(error_type, 0) + 1

    print("\nRESULTADO DOS TESTES:")
    print(f"Total de execuções: {NUM_TESTS}")
    print(f"✅ Acertos: {success_count}")
    print(f"❌ Erros: {error_count}")
    print(f"IDs de acertos: {success_ids}")
    print("Tipos de erro e quantidade:")
    for error, count in error_types_counts.items():
        print(f"  {error}: {count}")

if __name__ == "__main__":
    main()
