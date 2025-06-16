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
import random
import string # Para gerar letras aleatórias para mutação
from concurrent.futures import ThreadPoolExecutor, as_completed # Importações para paralelismo

# --- CONFIGURAÇÃO GLOBAL DE LOGS DO SCRAPER ---
ENABLE_SCRAPER_LOGS = False # Defina como False para desativar logs internos do scraper.
# ---------------------------------------------

# A FUNÇÃO log_callback AQUI AGORA É CONDICIONAL
# Ela será a função que o scraper_cloudflare.py usará.
if ENABLE_SCRAPER_LOGS:
    def scraper_internal_log_callback(message):
        """Função de callback real para logs do scraper (se ativados)."""
        print(f"[{time.strftime('%H:%M:%S')}] [SCRAPER] {message}") # Adicionado [SCRAPER] para diferenciar
else:
    def scraper_internal_log_callback(message):
        """Função de callback nula que não faz nada (desativa logs do scraper)."""
        pass # Não faz nada


# Esta é a log_callback para o script principal (example_scraper.py)
# Sempre imprime, para que você veja o progresso geral do teste.
def main_script_log(message):
    print(f"[{time.strftime('%H:%M:%S')}] [MAIN] {message}")


def _mutate_keywords(keywords_list, test_log_collector):
    """
    Introduz uma pequena mutação (troca de uma letra) em uma palavra-chave aleatória.
    Retorna uma nova lista com a palavra-chave mutada.
    """
    if not keywords_list:
        return []

    mutated_keywords = list(keywords_list) # Trabalha em uma cópia para não alterar a original diretamente
    
    # Seleciona uma palavra-chave aleatoriamente para mutar
    keyword_to_mutate_index = random.randint(0, len(mutated_keywords) - 1)
    original_keyword = mutated_keywords[keyword_to_mutate_index]
    
    if len(original_keyword) < 2: # Palavras muito curtas podem ser difícil de mutar sem perder sentido
        return mutated_keywords # Não muta se for muito curta
    
    # Seleciona uma posição aleatória na palavra para mutar
    char_index_to_mutate = random.randint(0, len(original_keyword) - 1)
    
    # Escolhe uma nova letra aleatoriamente (a-z)
    new_char = random.choice(string.ascii_lowercase)
    
    # Constrói a nova palavra-chave mutada
    mutated_word = list(original_keyword)
    mutated_word[char_index_to_mutate] = new_char
    mutated_keywords[keyword_to_mutate_index] = "".join(mutated_word)
    
    test_log_collector(f"🔄 Mutating keyword: '{original_keyword}' -> '{mutated_keywords[keyword_to_mutate_index]}'")
    
    return mutated_keywords


def run_until_failure_test(scraper_instance, test_case, negative_keywords, max_pages_per_call=1, max_total_calls=100):
    """
    Executa um teste de scraping medindo quantas chamadas consecutivas de sucesso são feitas
    até o primeiro erro. Contabiliza erros e quantas vezes o embaralhamento e/ou mutação ajudou a recuperar.
    Quando ocorre uma falha, tenta retentativas em duas fases:
    1. Até 3x apenas embaralhando a ordem das keywords.
    2. Se ainda falhar, muta uma keyword e embaralha nas tentativas restantes (até um total de 4).
    Todos os logs internos a este teste são coletados e impressos ao final.
    Retorna um dicionário com os resultados do teste e a string de logs.
    """
    test_name = test_case["name"]
    original_keywords = list(test_case["keywords"]) # Copia para não modificar a original
    
    # Lista para coletar os logs internos deste teste
    _test_logs = []
    def test_log_collector(message):
        _test_logs.append(f"[{time.strftime('%H:%M:%S')}] [TEST_INNER] {message}")

    consecutive_successful_calls = 0
    total_calls_attempted = 0
    errors_encountered = 0
    times_recovered_by_shuffling_only = 0 # Recuperação apenas com embaralhamento
    times_recovered_by_mutation = 0 # Recuperação com mutação (implica embaralhamento também)
    
    # Controla o ciclo de retentativas após uma falha
    retry_attempts_on_failure = 0
    MAX_SHUFFLE_RETRIES = 3 # Tentativas de reordenação após a primeira falha
    MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE = 4 # Total de tentativas extras (3 shuffle + 1 mutate)

    # Este é um rastreador crucial para o "recovered_by_shuffling"
    # Ele será True se a chamada IMEDIATAMENTE ANTERIOR resultou em um erro.
    last_call_resulted_in_error = False 
    
    test_log_collector(f"\n--- In Test: {test_name} (Repeating Until First Failure) ---")
    
    # Loop principal: Continua enquanto houver sucessos (ou até max_total_calls)
    while total_calls_attempted < max_total_calls:
        total_calls_attempted += 1
        
        # Decide qual conjunto de palavras-chave usar e se deve mutar
        keywords_for_current_attempt = list(original_keywords) # Começa com a original
        
        if last_call_resulted_in_error:
            # Se a chamada anterior falhou, incrementa o contador de retentativas.
            # O retry_attempts_on_failure será 1 na primeira retentativa, 2 na segunda, etc.
            retry_attempts_on_failure += 1 

            if retry_attempts_on_failure > MAX_SHUFFLE_RETRIES:
                # Se já tentou apenas embaralhar MAX_SHUFFLE_RETRIES vezes e falhou, então muta
                test_log_collector(f"🧠 Attempting mutation strategy (Retry {retry_attempts_on_failure}/{MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE})...")
                keywords_for_current_attempt = _mutate_keywords(original_keywords, test_log_collector) # Muta a lista ORIGINAL
            else:
                test_log_collector(f"🔄 Attempting shuffle-only strategy (Retry {retry_attempts_on_failure}/{MAX_SHUFFLE_RETRIES})...")
            
        # Sempre embaralha, independentemente de ser uma retentativa ou não, ou se houve mutação
        random.shuffle(keywords_for_current_attempt)
        
        test_log_collector(f"\n--- Call {total_calls_attempted} for '{test_name}' ---")
        test_log_collector(f"🎯 Attempting scrape with keywords: {', '.join(keywords_for_current_attempt)}")
        
        error_info = None # Resetar erro para esta chamada

        try:
            # Usando o método 'scrape_err' para que "nenhum anúncio encontrado" seja um erro explícito
            ads = scraper_instance.scrape_err(
                keywords=keywords_for_current_attempt,
                negative_keywords_list=negative_keywords,
                max_pages=max_pages_per_call,
                save_page=False
            )

            test_log_collector(f"\n📊 Test Results for '{test_name}' - Call {total_calls_attempted}:")
            test_log_collector(f"Total ads found: {len(ads)}")

            if ads: # Se encontrou anúncios, é um sucesso para o objetivo do teste
                test_log_collector(f"✅ Ads found. Successful call for '{test_name}'.")
                consecutive_successful_calls += 1
                
                # Rastrear o tipo de recuperação
                if last_call_resulted_in_error:
                    if retry_attempts_on_failure > MAX_SHUFFLE_RETRIES:
                        times_recovered_by_mutation += 1
                        test_log_collector(f"✨ Recovery detected! Mutation + Shuffling helped after previous error. Total mutation recoveries: {times_recovered_by_mutation}")
                    else:
                        times_recovered_by_shuffling_only += 1
                        test_log_collector(f"✨ Recovery detected! Shuffling only helped after previous error. Total shuffle-only recoveries: {times_recovered_by_shuffling_only}")
                
                last_call_resulted_in_error = False # Resetar o flag de falha, pois esta chamada foi um sucesso
                retry_attempts_on_failure = 0 # Resetar contador de retentativas
                
                # Pausa antes da próxima chamada consecutiva
                time.sleep(random.uniform(5, 15))
            else:
                # Embora scrape_err deva lançar exceção, esta é uma salvaguarda.
                test_log_collector(f"❌ No ads found for '{test_name}'. Breaking consecutive streak (no relevant ads found).")
                errors_encountered += 1 # Conta como erro (erro de negócio)
                last_call_resulted_in_error = True # A chamada atual resultou em erro (ausência de ads)
                
                # Lógica para continuar retentativas ou quebrar
                if retry_attempts_on_failure < MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE:
                    time.sleep(random.uniform(20, 60)) # Delay maior para retentativas
                    continue # Continua para a próxima iteração do while
                else:
                    test_log_collector(f"🚫 Max retry attempts ({MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE}) reached after consecutive 'no ads found' failures. Breaking streak.")
                    break # Quebra a sequência de sucessos
                
        except Exception as e:
            # Captura qualquer exceção lançada por scrape_err (HTTP, Cloudflare, ou ValueError de "página sem anúncios")
            test_log_collector(f"💥 Error during scrape for '{test_name}' in Call {total_calls_attempted}: {e}")
            test_log_collector(f"🚫 Consecutive success streak broken for '{test_name}'.")
            
            errors_encountered += 1 # Conta o erro
            last_call_resulted_in_error = True # A chamada atual resultou em erro (exceção)
            error_info = str(e)

            # Lógica para continuar retentativas ou quebrar
            if retry_attempts_on_failure < MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE:
                time.sleep(random.uniform(20, 60)) # Delay maior para retentativas
                continue # Continua para a próxima iteração do while
            else:
                test_log_collector(f"🚫 Max retry attempts ({MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE}) reached after consecutive failures. Breaking streak.")
                break # Quebra a sequência de sucessos ao primeiro erro (após retentativas)
    
    # Determinar o status final do teste
    final_status = ""
    if total_calls_attempted >= max_total_calls and not last_call_resulted_in_error:
        final_status = "COMPLETED_MAX_CALLS_WITH_SUCCESS" # Rodou todas as chamadas e teve sucesso na última
    elif errors_encountered > 0 and consecutive_successful_calls == 0:
        final_status = "FAILED_IMMEDIATELY_OR_AFTER_RETRIES" # Falhou no início ou após as retentativas e não teve sucesso
    elif errors_encountered > 0 and consecutive_successful_calls > 0:
        final_status = "STREAK_BROKEN_AFTER_SOME_SUCCESS_AND_RETRIES" # Teve alguns sucessos, mas falhou e não recuperou
    elif consecutive_successful_calls == 0: # Nenhuma chamada de sucesso em todas as tentativas
        final_status = "NO_SUCCESSFUL_CALLS_AT_ALL"
    else: # Outro caso, como quebrar por `no ads` antes de atingir max_total_calls e sem retentativas (improvável com a nova lógica)
        final_status = "UNEXPECTED_BREAK_CONDITION"

    return {
        "test_name": test_name,
        "final_status": final_status,
        "total_calls_attempted": total_calls_attempted,
        "consecutive_successful_calls_before_final_break": consecutive_successful_calls, # Renomeado para clareza
        "errors_encountered_total": errors_encountered, # Renomeado para clareza
        "times_recovered_by_shuffling_only": times_recovered_by_shuffling_only,
        "times_recovered_by_mutation": times_recovered_by_mutation,
        "max_total_calls_configured": max_total_calls,
        "max_retry_attempts_on_failure_configured": MAX_TOTAL_RETRY_ATTEMPTS_ON_FAILURE,
        "last_keywords_used": keywords_for_current_attempt if 'keywords_for_current_attempt' in locals() else original_keywords,
        "error_that_broke_streak": error_info,
        "test_logs": _test_logs # Retorna a lista de logs
    }


def main():
    # Carrega variáveis de ambiente
    load_dotenv()
    
    # Configurações através de variáveis de ambiente
    base_url = os.getenv("MAIN_URL_SCRAPE_ROXO", "https://www.olx.com.br")
    
    # Configuração do proxy (opcional)
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    proxy_config = http_proxy or https_proxy or ""
    
    # Palavras-chave padrão do .env (DEFAULT_KEYWORDS)
    default_keywords_str = os.getenv("DEFAULT_KEYWORDS", "bike,indoor,concept2,spinning,bicicleta,schwinn,technogym")
    default_keywords = [kw.strip() for kw in default_keywords_str.split(",") if kw.strip()]

    # Palavras-chave negativas (para filtrar)
    negative_keywords_str = os.getenv("NEGATIVE_KEYWORDS_LIST", "quebrada,defeito,peças,sucata")
    negative_keywords = [kw.strip() for kw in negative_keywords_str.split(",") if kw.strip()]
    
    # Número de páginas para buscar por chamada de scrape (para o teste de resiliência, geralmente 1)
    max_pages_per_scrape_call = 1
    
    # Inicializa o scraper (apenas uma instância, que será compartilhada pelas threads)
    scraper = MarketRoxoScraperCloudflare(
        log_callback=scraper_internal_log_callback, # Passa a função de log condicional
        base_url=base_url,
        proxies=proxy_config
    )

    # Define a list of test cases
    test_cases = [
        {
            "name": "Default Keywords from .env - Gym Equipment",
            "keywords": default_keywords
        },
        {
            "name": "Electronic Products - iPhones",
            "keywords": ["iphone", "apple"]
        },
        {
            "name": "Vehicles - Used Cars",
            "keywords": ["carro", "usado", "seminovo", "hatch", "sedan"]
        },
        {
            "name": "Home Furniture Scrape",
            "keywords": ["sofa", "mesa", "cadeira", "armario", "cama"]
        },
        {
            "name": "Camera Products Scrape",
            "keywords": ["camera", "fotografica", "nikon", "canon"]
        }
    ]

    all_test_results = []
    overall_test_suite_passed = True # Flag para indicar se todos os testes tiveram sucesso conforme seu critério

    main_script_log("\n--- Starting Comprehensive Consecutive Success Test Suite (Parallel Execution) ---")
    main_script_log("=" * 70)

    # Usar ThreadPoolExecutor para executar testes em paralelo
    with ThreadPoolExecutor(max_workers=len(test_cases)) as executor: # O número de workers pode ser ajustado
        futures = {executor.submit(run_until_failure_test, 
                                    scraper, 
                                    tc, 
                                    negative_keywords, 
                                    max_pages_per_scrape_call, 
                                    max_total_calls=20): tc["name"] 
                   for tc in test_cases}

        for future in as_completed(futures):
            test_name = futures[future]
            try:
                result = future.result()
                all_test_results.append(result)
                main_script_log(f"\n🏁 Teste '{test_name}' concluído. Status: {result['final_status']}")
                
                # Imprimir os logs coletados do teste específico
                if result.get("test_logs"):
                    main_script_log(f"\n--- Detailed Logs for Test: {test_name} ---")
                    for log_line in result["test_logs"]:
                        print(log_line) # Imprime cada linha de log acumulada
                    main_script_log(f"--- End Logs for Test: {test_name} ---")

                if result["consecutive_successful_calls_before_final_break"] == 0:
                    overall_test_suite_passed = False
            except Exception as exc:
                main_script_log(f"\n💥 Teste '{test_name}' gerou uma exceção: {exc}")
                overall_test_suite_passed = False
                all_test_results.append({
                    "test_name": test_name,
                    "final_status": "EXCEPTION_DURING_EXECUTION",
                    "error_info": str(exc),
                    "total_calls_attempted": "N/A",
                    "consecutive_successful_calls_before_final_break": 0,
                    "errors_encountered_total": "N/A",
                    "times_recovered_by_shuffling_only": "N/A",
                    "times_recovered_by_mutation": "N/A",
                    "max_total_calls_configured": 20,
                    "max_retry_attempts_on_failure_configured": 4,
                    "last_keywords_used": "N/A",
                    "error_that_broke_streak": str(exc),
                    "test_logs": [f"[{time.strftime('%H:%M:%S')}] [TEST_INNER] Exceção capturada: {exc}"] # Logs para exceção
                })
                # Imprimir os logs coletados do teste específico mesmo em caso de exceção
                if all_test_results[-1].get("test_logs"):
                    main_script_log(f"\n--- Detailed Logs for Test (Exception): {test_name} ---")
                    for log_line in all_test_results[-1]["test_logs"]:
                        print(log_line)
                    main_script_log(f"--- End Logs for Test (Exception): {test_name} ---")


    main_script_log("\n--- End of Comprehensive Consecutive Success Test Suite ---")
    main_script_log("=" * 70)

    # --- Returning Results for Analysis ---
    main_script_log("\n--- Test Results Summary for Analysis ---")
    for res in all_test_results:
        main_script_log(f"\nTest: {res['test_name']}")
        main_script_log(f"  Final Status: {res['final_status']}")
        main_script_log(f"  Total Calls Attempted: {res['total_calls_attempted']}")
        main_script_log(f"  Consecutive Successful Calls Before Final Break: {res['consecutive_successful_calls_before_final_break']}")
        main_script_log(f"  Errors Encountered (total): {res['errors_encountered_total']}")
        main_script_log(f"  Times Recovered by Shuffling Only: {res['times_recovered_by_shuffling_only']}")
        main_script_log(f"  Times Recovered by Mutation: {res['times_recovered_by_mutation']}")
        main_script_log(f"  Max Total Calls Configured: {res['max_total_calls_configured']}")
        main_script_log(f"  Max Retry Attempts on Failure (total): {res['max_retry_attempts_on_failure_configured']}")
        main_script_log(f"  Last Keywords Used: {', '.join(res['last_keywords_used']) if isinstance(res['last_keywords_used'], list) else res['last_keywords_used']}")
        if res['error_that_broke_streak']:
            main_script_log(f"  Error that broke streak: {res['error_that_broke_streak']}")
        main_script_log(f"  Total Recoveries (Shuffling or Mutation): {res['times_recovered_by_shuffling_only'] + res['times_recovered_by_mutation'] if isinstance(res['times_recovered_by_shuffling_only'], int) else 'N/A'}")

    return overall_test_suite_passed

if __name__ == "__main__":
    import time 
    
    print("🚀 MarketRoxo Scraper with Cloudflare Bypass - Automated Tests")
    print("=" * 70)
    
    final_test_suite_status = main()
    
    if final_test_suite_status:
        print("\n✅ All test suites completed with at least one consecutive success and passed criteria!")
    else:
        print("\n❌ Some test suites failed to achieve any consecutive successful calls or did not meet success criteria.")