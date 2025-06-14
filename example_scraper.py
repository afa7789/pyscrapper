#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exemplo de uso do MarketRoxoScraper2 com bypass Cloudflare
"""

from scraper_2 import MarketRoxoScraper2
import json
import os
from dotenv import load_dotenv

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
    
    # Palavras-chave para buscar
    keywords_str = os.getenv("DEFAULT_KEYWORDS", "bike,indoor,concept2,spinning,bicicleta,schwinn,technogym")
    keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
    
    # Palavras-chave negativas (para filtrar)
    negative_keywords_str = os.getenv("NEGATIVE_KEYWORDS_LIST", "quebrada,defeito,peças,sucata")
    negative_keywords = [kw.strip() for kw in negative_keywords_str.split(",") if kw.strip()]
    
    # Número de páginas para buscar
    max_pages = 2
    
    # Salvar páginas para debug
    save_page = False
    
    # Inicializa o scraper
    scraper = MarketRoxoScraper2(
        log_callback=log_callback,
        base_url=base_url,
        proxies=proxy_config
    )
    
    try:
        # Executa o scraping
        print("🎯 Iniciando busca por anúncios...")
        ads = scraper.scrape(
            keywords=keywords,
            negative_keywords_list=negative_keywords,
            max_pages=max_pages,
            save_page=save_page
        )
        
        # Exibe resultados
        print(f"\n📊 RESULTADO FINAL:")
        print(f"Total de anúncios encontrados: {len(ads)}")
        
        if ads:
            print("\n📋 Anúncios encontrados:")
            for i, ad in enumerate(ads, 1):
                print(f"{i}. {ad['title']}")
                print(f"   URL: {ad['url']}")
                print()
            
            # Salva resultados em arquivo JSON
            output_file = os.getenv("OUTPUT_FILE", "anuncios_encontrados.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(ads, f, ensure_ascii=False, indent=2)
            print(f"💾 Resultados salvos em '{output_file}'")
        else:
            print("❌ Nenhum anúncio encontrado com os critérios especificados.")
            
    except Exception as e:
        print(f"💥 Erro durante o scraping: {e}")
        return False
    
    return True

if __name__ == "__main__":
    import time
    
    print("🚀 MarketRoxo Scraper com Bypass Cloudflare")
    print("=" * 50)
    
    success = main()
    
    if success:
        print("\n✅ Scraping concluído com sucesso!")
    else:
        print("\n❌ Scraping falhou!")