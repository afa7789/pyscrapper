#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exemplo de uso do MarketRoxoScraper2 com bypass Cloudflare
"""

from scraper_cloudflare import MarketRoxoScraperCloudflare
import json
import os
from dotenv import load_dotenv
import time
import random  # Import random for delay

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
    proxy_config = http_proxy or https_proxy or ""
    use_proxy = True # Verifica se o proxy está configurado
    
    keywords_str = os.getenv("DEFAULT_KEYWORDS", "bike,indoor,concept2,spinning,bicicleta,schwinn,technogym")
    keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]

    # Palavras-chave negativas (para filtrar)
    negative_keywords_str = os.getenv("NEGATIVE_KEYWORDS_LIST", "quebrada,defeito,peças,sucata")
    negative_keywords = [kw.strip() for kw in negative_keywords_str.split(",") if kw.strip()]
    
    # Número de páginas para buscar
    max_pages = 1
    
    # Salvar páginas para debug
    save_page = False
    
    # Inicializa o scraper sem proxy se proxy_config estiver vazio
    if proxy_config and use_proxy:
        scraper = MarketRoxoScraperCloudflare(
            log_callback=log_callback,
            base_url=base_url,
            proxies=proxy_config
        )
    else:
        scraper = MarketRoxoScraperCloudflare(
            log_callback=log_callback,
            base_url=base_url
        )
    
    # Teste inicial de scrape err c/ marketroxo, repetindo até ter sucesso
    attempt = 0
    error_counts = {}
    error_messages = []  # Armazena mensagens únicas de erro
    
    while True:
        try:
            attempt += 1
            print(f"🎯 Iniciando busca por anúncios... Tentativa {attempt}")
            current_keywords_for_loop = keywords
            print(f"\n🔍 Buscando anúncios com as palavras-chave: {', '.join(current_keywords_for_loop)}")
            
            ads = scraper.scrape_err(
                query_keywords=current_keywords_for_loop, 
                keywords=current_keywords_for_loop,
                negative_keywords_list=negative_keywords,
                max_pages=max_pages,
                save_page=save_page
            )
            
            # Exibe resultados
            print(f"\n📊 RESULTADO FINAL:")
            print(f"Total de anúncios encontrados: {len(ads)}")
            break  # Sai do loop em caso de sucesso
            
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            # Armazena uma representação única da mensagem de erro
            if f"{error_type}: {error_message}" not in error_messages:
                error_messages.append(f"{error_type}: {error_message}")
            
            print(f"💥 Erro durante o scraping (Tentativa {attempt}): {error_type} - {error_message}")
            print(f"Erros acumulados: {error_counts}")
            
            # Adiciona delay aleatório entre tentativas (entre 2 e 5 segundos)
            delay = random.uniform(3, 50)
            print(f"⏳ Aguardando {delay:.2f} segundos antes de tentar novamente...")
            time.sleep(delay)

    # --- Resumo dos Erros ---
    if error_counts:
        print("\n--- ERRO SUMMARY ---")
        for error_type, count in error_counts.items():
            print(f"Error Type: {error_type}, Occurrences: {count}")
        
        if error_messages:
            print("\nMessages:")
            for msg in error_messages:
                print(f"- {msg}")
    # --- Fim do Resumo dos Erros ---

    return True  # Indica que o processo de scraping terminou (com sucesso ou após tentativas)

if __name__ == "__main__":
    
    print("🚀 MarketRoxo Scraper com Bypass Cloudflare")
    print("=" * 50)
    
    success = main()
    
    if success:
        print("\n✅ Scraping concluído com sucesso!")
    else:
        print("\n❌ Scraping falhou!")