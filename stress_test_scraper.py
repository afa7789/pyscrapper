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
import string
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from rich.progress import Progress, TaskID
import threading
import queue

# --- CONFIGURAÇÃO GLOBAL DE LOGS DO SCRAPER ---
ENABLE_SCRAPER_LOGS = False
# ---------------------------------------------

# A FUNÇÃO log_callback AQUI AGORA É CONDICIONAL
# Ela será a função que o scraper_cloudflare.py usará.
if ENABLE_SCRAPER_LOGS:
    def scraper_internal_log_callback(message):
        """Função de callback real para logs do scraper (se ativados)."""
        print(f"[{time.strftime("%H:%M:%S")}] [SCRAPER] {message}") # Adicionado [SCRAPER] para diferenciar
else:
    def scraper_internal_log_callback(message):
        """Função de callback nula que não faz nada (desativa logs do scraper)."""
        pass # Não faz nada


# Esta é a log_callback para o script principal (example_scraper.py)
# Sempre imprime, para que você veja o progresso geral do teste.
def main_script_log(message):
    print(f"[{time.strftime("%H:%M:%S")}] [MAIN] {message}")


def _mutate_keywords(keywords_list, test_log_collector, num_mutations=1):
    """
    Introduz múltiplas mutações nas keywords, sempre baseando nas originais.
    
    Args:
        keywords_list: Lista original de keywords
        test_log_collector: Função para logging
        num_mutations: Número de mutações a aplicar
    
    Returns:
        Nova lista com keywords mutadas
    """
    if not keywords_list or num_mutations <= 0:
        return list(keywords_list)

    mutated_keywords = list(keywords_list)  # Trabalha com cópia
    mutations_applied = 0
    
    # Aplica o número solicitado de mutações
    for mutation_round in range(num_mutations):
        if mutations_applied >= len(mutated_keywords):
            break  # Não pode mutar mais do que o número de palavras disponíveis
            
        # Seleciona uma palavra-chave que ainda não foi mutada nesta rodada
        available_indices = list(range(len(mutated_keywords)))
        
        if not available_indices:
            break
            
        keyword_to_mutate_index = random.choice(available_indices)
        original_keyword = mutated_keywords[keyword_to_mutate_index]
        
        if len(original_keyword) < 2:
            continue  # Pula palavras muito curtas
        
        # Seleciona uma posição aleatória na palavra para mutar
        char_index_to_mutate = random.randint(0, len(original_keyword) - 1)
        
        # Escolhe uma nova letra aleatoriamente
        new_char = random.choice(string.ascii_lowercase)
        
        # Constrói a nova palavra-chave mutada
        mutated_word = list(original_keyword)
        mutated_word[char_index_to_mutate] = new_char
        mutated_keywords[keyword_to_mutate_index] = "".join(mutated_word)
        
        test_log_collector(f"🔄 Mutation {mutation_round + 1}: '{original_keyword}' -> '{mutated_keywords[keyword_to_mutate_index]}'")
        mutations_applied += 1
    
    test_log_collector(f"🎯 Applied {mutations_applied} mutations total")
    return mutated_keywords

def _remove_random_keyword(keywords_list, test_log_collector, min_keywords=2):
    """
    Remove uma palavra-chave aleatória da lista, garantindo um número mínimo.
    
    Args:
        keywords_list: Lista de keywords atual.
        test_log_collector: Função para logging.
        min_keywords: Número mínimo de keywords a serem mantidas na lista.
        
    Returns:
        Nova lista de keywords com uma removida, ou a mesma lista se o mínimo for atingido.
    """
    if len(keywords_list) > min_keywords:
        keyword_to_remove = random.choice(keywords_list)
        new_keywords_list = [kw for kw in keywords_list if kw != keyword_to_remove]
        test_log_collector(f"🗑️ Removed keyword: '{keyword_to_remove}'. New list: {", ".join(new_keywords_list)}")
        return new_keywords_list
    else:
        test_log_collector(f"⚠️ Cannot remove keyword. Minimum of {min_keywords} keywords reached.")
        return list(keywords_list) # Retorna uma cópia para evitar modificações inesperadas

# ========================== RICH PROGRESS BAR SETUP ==========================
class ProgressUpdater:
    """Thread-safe progress bar updater using a queue"""
    def __init__(self):
        self.queue = queue.Queue()
        self.progress = Progress()
        self.task_map = {}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._update_worker, daemon=True)
        
    def start(self):
        self.thread.start()
        return self.progress
        
    def stop(self):
        self.stop_event.set()
        self.thread.join()
        
    def add_task(self, description, total):
        task_id = self.progress.add_task(description, total=total)
        self.task_map[description] = task_id
        return task_id
        
    def update(self, description, advance=1):
        if description in self.task_map:
            self.queue.put((self.task_map[description], advance))
            
    def _update_worker(self):
        while not self.stop_event.is_set():
            try:
                task_id, advance = self.queue.get(timeout=0.1)
                self.progress.update(task_id, advance=advance)
                self.queue.task_done()
            except queue.Empty:
                pass
# ============================================================================

def run_until_failure_test(scraper_instance, test_case, negative_keywords, 
                           max_pages_per_call=1, max_total_calls=100, 
                           min_keywords_to_keep=2, progress_updater=None):
    """
    Executa um teste de scraping com estratégia avançada de retry e condições de parada aprimoradas.

    Condições de Parada:
    - Atingir `max_total_calls` (padrão: 100).
    - Obter `SUCCESS_STREAK_THRESHOLD` sucessos consecutivos (padrão: 5).

    A estratégia de retry é dividida em fases sequenciais, baseadas no número de falhas consecutivas:

    Fase 0 (Tentativas 1-10): Sem embaralhamento (no_shuffle).
    Fase 1 (Tentativas 1-10, após falha na Fase 0): Apenas embaralhamento (shuffle_only).
    Fase 2 (Tentativas 11-25): Embaralhamento + 1 mutação leve (shuffle_1_mutation).
    Fase 3 (Tentativas 26-50): Embaralhamento + 2 mutações (shuffle_2_mutations).
    Fase 4 (Tentativas 51-75): Embaralhamento + 3 mutações (shuffle_3_mutations).
    Fase 5 (Tentativas 76-100): Embaralhamento + 4 ou mais mutações progressivamente (shuffle_4+_mutations).

    Além disso, após uma falha, uma palavra-chave pode ser removida da lista, até um mínimo de `min_keywords_to_keep`.
    Cada fase testa um nível crescente de alteração no comportamento do scraping.
    """
    test_name = test_case["name"]
    # Mantém a lista original de keywords para resetar ou mutar a partir dela
    original_keywords_base = list(test_case["keywords"])
    # Lista de keywords que será usada na tentativa atual, pode ser modificada (removida, mutada, embaralhada)
    current_keywords_for_test = list(original_keywords_base)
    
    # Limite de sucessos consecutivos para parar o teste
    SUCCESS_STREAK_THRESHOLD = 5

    # Lista para coletar os logs internos deste teste
    _test_logs = []
    def test_log_collector(message):
        _test_logs.append(f"[{time.strftime("%H:%M:%S")}] [TEST_INNER] {message}")

    consecutive_successful_calls = 0
    total_calls_attempted = 0
    errors_encountered = 0
    
    # Rastreamento detalhado de metodologias
    methodology_success_count = {
        "no_shuffle": 0,
        "shuffle_only": 0,
        "shuffle_1_mutation": 0,
        "shuffle_2_mutations": 0,
        "shuffle_3_mutations": 0,
        "shuffle_4+_mutations": 0,
        "keyword_removal": 0 # Nova métrica para remoção de keywords
    }
    
    methodology_recovery_count = {
        "no_shuffle": 0,
        "shuffle_only": 0,
        "shuffle_1_mutation": 0,
        "shuffle_2_mutations": 0,
        "shuffle_3_mutations": 0,
        "shuffle_4+_mutations": 0,
        "keyword_removal": 0
    }
    
    # Controla o ciclo de retentativas após uma falha
    consecutive_failures = 0  # Contador de falhas consecutivas
    last_call_resulted_in_error = False 
    current_strategy = "no_shuffle" # Estratégia inicial
    
    test_log_collector(f"\n--- In Test: {test_name} (Advanced Retry Strategy - Up to {max_total_calls} calls) ---")
    test_log_collector(f"📋 Original Keywords: {", ".join(original_keywords_base)}")
    
    # Create progress task if updater is provided
    task_description = f"Test: {test_name}"
    if progress_updater:
        progress_updater.add_task(task_description, total=max_total_calls)

    # Loop principal
    while total_calls_attempted < max_total_calls and consecutive_successful_calls < SUCCESS_STREAK_THRESHOLD:
        total_calls_attempted += 1
        
        # Update progress bar if available
        if progress_updater:
            progress_updater.update(task_description)

        # Se a chamada anterior resultou em erro, incrementa o contador de falhas
        # e tenta uma nova estratégia
        if last_call_resulted_in_error:
            consecutive_failures += 1
            # Tenta remover uma keyword se a lista ainda for grande o suficiente
            if len(current_keywords_for_test) > min_keywords_to_keep:
                current_keywords_for_test = _remove_random_keyword(current_keywords_for_test, test_log_collector, min_keywords=min_keywords_to_keep)
                methodology_recovery_count["keyword_removal"] += 1 # Registra tentativa de recuperação por remoção
                test_log_collector(f"🗑️ Attempting recovery by keyword removal. Current keywords: {", ".join(current_keywords_for_test)}")
            
            # Define estratégia baseada no número de tentativas de retry (consecutive_failures)
            # A lógica de fases agora começa após a primeira falha
            if consecutive_failures <= 10:
                # Fase 1: Apenas shuffle (tentativas 1-10 após primeira falha)
                random.shuffle(current_keywords_for_test)
                current_strategy = "shuffle_only"
                test_log_collector(f"🔄 Strategy Phase 1 - Shuffle Only (Retry {consecutive_failures}/10)")
                
            elif consecutive_failures <= 25:
                # Fase 2: Shuffle + 1 mutação (tentativas 11-25)
                # Muta a partir da lista original, não da lista já modificada pela remoção
                current_keywords_for_test = _mutate_keywords(original_keywords_base, test_log_collector, num_mutations=1)
                random.shuffle(current_keywords_for_test)
                current_strategy = "shuffle_1_mutation"
                test_log_collector(f"🧬 Strategy Phase 2 - Shuffle + 1 Mutation (Retry {consecutive_failures}/25)")
                
            elif consecutive_failures <= 50:
                # Fase 3: Shuffle + 2 mutações (tentativas 26-50)
                current_keywords_for_test = _mutate_keywords(original_keywords_base, test_log_collector, num_mutations=2)
                random.shuffle(current_keywords_for_test)
                current_strategy = "shuffle_2_mutations"
                test_log_collector(f"🧬🧬 Strategy Phase 3 - Shuffle + 2 Mutations (Retry {consecutive_failures}/50)")
                
            elif consecutive_failures <= 75:
                # Fase 4: Shuffle + 3 mutações (tentativas 51-75)
                current_keywords_for_test = _mutate_keywords(original_keywords_base, test_log_collector, num_mutations=3)
                random.shuffle(current_keywords_for_test)
                current_strategy = "shuffle_3_mutations"
                test_log_collector(f"🧬🧬🧬 Strategy Phase 4 - Shuffle + 3 Mutations (Retry {consecutive_failures}/75)")
                
            else:
                # Fase 5: Shuffle + mutação progressiva (tentativas 76+)
                # O número de mutações aumenta a cada 5 falhas após a tentativa 75
                num_mutations = min(4 + ((consecutive_failures - 75) // 5), len(original_keywords_base))
                current_keywords_for_test = _mutate_keywords(original_keywords_base, test_log_collector, num_mutations=num_mutations)
                random.shuffle(current_keywords_for_test)
                current_strategy = "shuffle_4+_mutations"
                test_log_collector(f"🧬✨ Strategy Phase 5 - Shuffle + {num_mutations} Mutations (Retry {consecutive_failures}/100)")
        else:
            # Se não houve erro na chamada anterior, reseta para as keywords originais
            # e aplica a estratégia da Fase 0 (no_shuffle) para as primeiras 10 chamadas
            # ou se a estratégia anterior foi bem-sucedida e queremos testar o 'no_shuffle' novamente
            if total_calls_attempted <= 10 and not last_call_resulted_in_error:
                current_keywords_for_test = list(original_keywords_base) # Sem embaralhamento
                current_strategy = "no_shuffle"
                test_log_collector(f"🎯 Strategy Phase 0 - No Shuffle (Call {total_calls_attempted}/10)")
            else:
                # Se já passou da fase 0 e não houve erro, continua com a estratégia que deu certo
                # ou reseta para a original e aplica shuffle_only se for a primeira tentativa após um sucesso
                current_keywords_for_test = list(original_keywords_base)
                random.shuffle(current_keywords_for_test)
                current_strategy = "shuffle_only" # Volta para shuffle_only como base após sucesso
                test_log_collector(f"🔄 Resetting to Shuffle Only after success (Call {total_calls_attempted})")

        test_log_collector(f"\n--- Call {total_calls_attempted} for \'{test_name}\' ---")
        test_log_collector(f"📊 Strategy: {current_strategy}")
        test_log_collector(f"🎯 Keywords: {", ".join(current_keywords_for_test)}")
        
        error_info = None

        try:
            ads = scraper_instance.scrape_err(
                keywords=current_keywords_for_test,
                negative_keywords_list=negative_keywords,
                max_pages=max_pages_per_call,
                save_page=False
            )

            test_log_collector(f"\n📊 Test Results for \'{test_name}\' - Call {total_calls_attempted}:")
            test_log_collector(f"Total ads found: {len(ads)}")

            if ads:
                test_log_collector(f"✅ Ads found. Successful call for \'{test_name}\' using strategy: {current_strategy}")
                consecutive_successful_calls += 1
                
                # Registra sucesso da metodologia
                methodology_success_count[current_strategy] += 1
                
                # Rastrear o tipo de recuperação
                if last_call_resulted_in_error:
                    methodology_recovery_count[current_strategy] += 1
                    test_log_collector(f"✨ Recovery by {current_strategy.upper()} after {consecutive_failures} failures! Total {current_strategy} recoveries: {methodology_recovery_count[current_strategy]}")
                
                # Reset counters após sucesso
                last_call_resulted_in_error = False
                consecutive_failures = 0
                
                # Pausa antes da próxima chamada
                time.sleep(random.uniform(5, 15)) # Pequena pausa após sucesso
            else:
                test_log_collector(f"❌ No ads found for \'{test_name}\' using strategy: {current_strategy}")
                errors_encountered += 1
                last_call_resulted_in_error = True
                consecutive_successful_calls = 0 # Reseta a contagem de sucessos consecutivos
                time.sleep(random.uniform(20, 60)) # Pausa maior após falha
                
        except Exception as e:
            test_log_collector(f"💥 Error during scrape for \'{test_name}\' in Call {total_calls_attempted} using strategy {current_strategy}: {e}")
            errors_encountered += 1
            last_call_resulted_in_error = True
            consecutive_successful_calls = 0 # Reseta a contagem de sucessos consecutivos
            error_info = str(e)
            time.sleep(random.uniform(20, 60)) # Pausa maior após falha
    
    # Determinar o status final do teste
    final_status = ""
    if consecutive_successful_calls >= SUCCESS_STREAK_THRESHOLD:
        final_status = "SUCCESS_STREAK_ACHIEVED"
    elif total_calls_attempted >= max_total_calls and not last_call_resulted_in_error:
        final_status = "COMPLETED_MAX_CALLS_WITH_SUCCESS"
    elif errors_encountered > 0 and consecutive_successful_calls == 0:
        final_status = "FAILED_ALL_ATTEMPTS"
    elif errors_encountered > 0 and consecutive_successful_calls > 0:
        final_status = "PARTIAL_SUCCESS_WITH_FINAL_FAILURES"
    else:
        final_status = "UNEXPECTED_CONDITION"

    # Calcular estatísticas das metodologias
    total_recoveries = sum(methodology_recovery_count.values())
    most_successful_methodology = max(methodology_success_count.items(), key=lambda x: x[1])
    most_recovery_methodology = max(methodology_recovery_count.items(), key=lambda x: x[1]) if total_recoveries > 0 else ("none", 0)

    return {
        "test_name": test_name,
        "final_status": final_status,
        "total_calls_attempted": total_calls_attempted,
        "consecutive_successful_calls_before_final_break": consecutive_successful_calls,
        "errors_encountered_total": errors_encountered,
        "consecutive_failures_at_end": consecutive_failures,
        "max_total_calls_configured": max_total_calls,
        "last_keywords_used": current_keywords_for_test if 'current_keywords_for_test' in locals() else original_keywords_base,
        "error_that_broke_streak": error_info,
        
        # Estatísticas detalhadas das metodologias
        "methodology_success_count": methodology_success_count,
        "methodology_recovery_count": methodology_recovery_count,
        "total_recoveries": total_recoveries,
        "most_successful_methodology": most_successful_methodology,
        "most_recovery_methodology": most_recovery_methodology,
        
        # Estatísticas legadas (para compatibilidade)
        "times_recovered_by_shuffling_only": methodology_recovery_count["shuffle_only"],
        "times_recovered_by_mutation": sum([
            methodology_recovery_count["shuffle_1_mutation"],
            methodology_recovery_count["shuffle_2_mutations"], 
            methodology_recovery_count["shuffle_3_mutations"],
            methodology_recovery_count["shuffle_4+_mutations"]
        ]),
        
        "test_logs": _test_logs
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

    max_total_calls_on_test = 15
    
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

    # Initialize rich progress system
    progress_updater = ProgressUpdater()
    
    main_script_log("\n--- Starting Comprehensive Consecutive Success Test Suite (Parallel Execution) ---")
    main_script_log("=" * 70)

    # Start progress bar thread
    with progress_updater.start():
        all_test_results = []
        overall_test_suite_passed = True

        # Usar ThreadPoolExecutor para executar testes em paralelo
        with ThreadPoolExecutor(max_workers=len(test_cases)) as executor: # O número de workers pode ser ajustado
            futures = {executor.submit(run_until_failure_test, 
                                        scraper, 
                                        tc, 
                                        negative_keywords, 
                                        max_pages_per_scrape_call, 
                                        max_total_calls=max_total_calls_on_test,
                                        min_keywords_to_keep=2,
                                        progress_updater=progress_updater): tc["name"] 
                       for tc in test_cases}

            for future in as_completed(futures):
                test_name = futures[future]
                try:
                    result = future.result()
                    all_test_results.append(result)
                    main_script_log(f"\n🏁 Teste \'{test_name}\' concluído. Status: {result["final_status"]}")
                    main_script_log(f"  Total de chamadas tentadas: {result["total_calls_attempted"]}")
                    main_script_log(f"  Chamadas bem-sucedidas consecutivas: {result["consecutive_successful_calls_before_final_break"]}")
                    main_script_log(f"  Erros encontrados: {result["errors_encountered_total"]}")
                    main_script_log(f"  Falhas consecutivas no final: {result["consecutive_failures_at_end"]}")
                    main_script_log(f"  Últimas keywords usadas: {", ".join(result["last_keywords_used"])}")
                    if result["error_that_broke_streak"]:
                        main_script_log(f"  Erro que quebrou a sequência: {result["error_that_broke_streak"]}")
                    
                    main_script_log("  --- Estatísticas de Metodologia ---")
                    for method, count in result["methodology_success_count"].items():
                        main_script_log(f"    Sucessos com \'{method}\': {count}")
                    for method, count in result["methodology_recovery_count"].items():
                        if count > 0:
                            main_script_log(f"    Recuperações com \'{method}\': {count}")
                    main_script_log(f"  Metodologia mais bem-sucedida: {result["most_successful_methodology"][0]} ({result["most_successful_methodology"][1]} sucessos)")
                    if result["total_recoveries"] > 0:
                        main_script_log(f"  Metodologia com mais recuperações: {result["most_recovery_methodology"][0]} ({result["most_recovery_methodology"][1]} recuperações)")
                    else:
                        main_script_log("  Nenhuma recuperação registrada.")

                    # Verifica se o teste falhou completamente
                    if result["final_status"] == "FAILED_ALL_ATTEMPTS":
                        overall_test_suite_passed = False

                except Exception as exc:
                    main_script_log(f"❌ Teste \'{test_name}\' gerou uma exceção: {exc}")
                    overall_test_suite_passed = False
                    all_test_results.append({"test_name": test_name, "final_status": "EXCEPTION", "error": str(exc)})
        
        # Stop progress updater after all tasks complete
        progress_updater.stop()

    main_script_log("\n" + "=" * 70)
    if overall_test_suite_passed:
        main_script_log("🎉 Todos os testes da suíte concluíram com sucesso (ou com sucesso parcial conforme o critério).")
    else:
        main_script_log("💔 Alguns testes da suíte falharam completamente ou geraram exceções.")
    main_script_log("--- Teste de Sucesso Consecutivo Abrangente Concluído ---")

    # Opcional: Salvar resultados em um arquivo JSON
    output_filename = "stress_test_results.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_test_results, f, ensure_ascii=False, indent=4)
    main_script_log(f"Resultados detalhados salvos em {output_filename}")

if __name__ == "__main__":
    main()