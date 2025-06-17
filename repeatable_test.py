#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para testar a ideia de scraping repetido de forma sequencial.
Executa em modo de teste com logs silenciosos, salvo erros em arquivo.
"""

import os
import time
import traceback
import logging
from dotenv import load_dotenv
from tqdm import tqdm
from scraper_cloudflare import MarketRoxoScraperCloudflare

# CONSTANTE: número de execuções do teste
NUM_TESTS = 10

def setup_logging():
    """Configura logging para arquivo de erros."""
    logging.basicConfig(
        filename="scraper_test_errors.log",
        level=logging.ERROR,
        format="%(asctime)s - %(message)s"
    )

def log_callback(message):
    """Callback de logs para console (usado apenas para progresso)."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def run_test(i, base_url, proxy_config, keywords, negative_keywords, max_pages, save_page, effective_callback):
    """Executa um único teste de scraping."""
    if i % 10 == 0:  # Log a cada 10 testes para evitar spam
        effective_callback(f"Running test index: {i}")
    scraper = MarketRoxoScraperCloudflare(
        log_callback=effective_callback,
        base_url=base_url,
        proxies=proxy_config
    )
    try:
        # Nota: save_page aqui controla se o HTML será salvo em caso de falha de EXTRAÇÃO.
        # Erros HTTP ainda podem ter seu HTML salvo se a lógica estiver em scraper_cloudflare.py
        scraper.scrape_err(
            keywords=keywords,
            negative_keywords_list=negative_keywords,
            max_pages=max_pages,
            save_page=save_page
        )
        return {
            "index": i,
            "success": True,
            "error_type": None,
            "error_msg": None,
            "traceback": None
        }
    except Exception as e:
        error_info = {
            "index": i,
            "success": False,
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "traceback": traceback.format_exc()
        }
        logging.error(f"Test {i} failed: {error_info['error_type']} - {error_info['error_msg']}\n{error_info['traceback']}")
        return error_info
    finally:
        try:
            # Assumindo que MarketRoxoScraperCloudflare possa ter um método close()
            # para liberar recursos como sessões, etc. Se não existir, ignore.
            if hasattr(scraper, 'close') and callable(scraper.close):
                scraper.close()
        except Exception as e:
            effective_callback(f"Warning: Failed to close scraper: {e}")


def main():
    """
    Executa o scraping repetido para teste de forma sequencial.
    Registra resultados e erros, com delay dinâmico entre tentativas.
    """
    load_dotenv()
    setup_logging()

    # Carrega configurações do ambiente
    base_url = os.getenv("MAIN_URL_SCRAPE_ROXO", "https://www.olx.com.br")
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    proxy_config = {
        "http": http_proxy,
        "https": https_proxy
    } if http_proxy or https_proxy else None

    keywords_str = os.getenv("DEFAULT_KEYWORDS", "bike,indoor,concept2,spinning,bicicleta,schwinn,technogym")
    keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
    if not keywords:
        raise ValueError("No valid keywords provided")

    negative_keywords_str = os.getenv("NEGATIVE_KEYWORDS_LIST", "quebrada,defeito,peças,sucata")
    negative_keywords = [kw.strip() for kw in negative_keywords_str.split(",") if kw.strip()]

    max_pages = int(os.getenv("MAX_PAGES", 2))
    save_page = os.getenv("SAVE_PAGE", "False").lower() == "true" # Passa para o scraper_cloudflare.py

    # Callback silencioso para testes (não imprime logs internos do scraper na console)
    effective_callback = lambda msg: None

    success_count = 0
    error_count = 0
    success_ids = []
    error_types_counts = {}
    results = [] # Para armazenar os resultados brutos de cada teste

    log_callback(f"🚀 Iniciando {NUM_TESTS} testes sequenciais com MarketRoxo Scraper (modo teste)")

    delay_seconds = 5  # Delay inicial
    max_delay = 30  # Limite máximo para delay
    for i in tqdm(range(NUM_TESTS), desc="Running tests"):
        result = run_test(i, base_url, proxy_config, keywords, negative_keywords, max_pages, save_page, effective_callback)
        results.append(result)
        if result["success"]:
            success_count += 1
            success_ids.append(result["index"])
            delay_seconds = 5  # Reseta delay após sucesso
        else:
            error_count += 1
            error_types_counts[result["error_type"]] = error_types_counts.get(result["error_type"], 0) + 1
            delay_seconds = min(delay_seconds + 5, max_delay)  # Incrementa delay, com limite

        # Log de progresso do delay, visível mesmo com effective_callback silencioso
        if i < NUM_TESTS - 1: # Não exibe o delay após o último teste
            log_callback(f"Executando próximo teste em {delay_seconds} segundo(s)...")
            time.sleep(delay_seconds)

    # Resumo final dos resultados (o que você quer ver)
    log_callback("\nRESULTADO DOS TESTES:")
    log_callback(f"Total de execuções: {NUM_TESTS}")
    log_callback(f"✅ Acertos: {success_count}")
    log_callback(f"❌ Erros: {error_count}")
    log_callback(f"IDs de acertos: {sorted(success_ids)}")
    log_callback("Tipos de erro e quantidade:")
    for error, count in error_types_counts.items():
        log_callback(f"  {error}: {count}")

    # A parte abaixo foi removida para atender à sua solicitação
    # log_callback("\nResumo detalhado dos erros:")
    # for r in results:
    #     if not r["success"]:
    #         log_callback(f"Index {r['index']}: {r['error_type']} - {r['error_msg']}")

if __name__ == "__main__":
    main()