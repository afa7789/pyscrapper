# monitor.py

import threading
import time
from datetime import datetime, timezone, timedelta
import random
import hashlib
import os
from emoji_sorter import get_random_emoji
from itertools import permutations

class Monitor:
    def __init__(self, keywords, negative_keywords_list, scraper, telegram_bot, chat_id, log_callback, hash_file=None, batch_size=20):
        self.keywords = keywords
        self.negative_keywords_list = negative_keywords_list
        self.scraper = scraper
        self.telegram_bot = telegram_bot
        self.chat_id = chat_id
        self.log_callback = log_callback
        self.running = False
        self.stop_event = threading.Event() # <--- ADD THIS LINE

        # Use home directory for the hash file if not specified
        if hash_file is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".marketroxo_data")
            os.makedirs(data_dir, exist_ok=True)
            self.hash_file = os.path.join(data_dir, "seen_ads.txt")
            self.log_callback(f"📁 Using hash file at: {self.hash_file}")
        else:
            self.hash_file = hash_file

        self.batch_size = batch_size
        self.seen_ads = self._load_seen_ads()
        
        # Dynamic interval settings
        self.base_interval_minutes = 20
        self.max_interval_minutes = 50
        self.interval_multiplier = 5
        self.current_interval_minutes = self.base_interval_minutes
        self.incomplete_page_count = 0
        self.incomplete_page_threshold = 3

    def _hash_ad(self, ad):
        return hashlib.sha256(ad['url'].encode('utf-8')).hexdigest()

    def _load_seen_ads(self):
        seen = set()
        if os.path.exists(self.hash_file):
            try:
                with open(self.hash_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        hash_value = line.strip()
                        if hash_value:
                            seen.add(hash_value)
                self.log_callback(f"📂 Carregados {len(seen)} anúncios vistos anteriormente")
            except Exception as e:
                self.log_callback(f"❌ Erro ao carregar anúncios vistos: {str(e)}")
        return seen

    def _save_ad_hash(self, ad_hash):
        try:
            with open(self.hash_file, 'a', encoding='utf-8') as f:
                f.write(f"{ad_hash}\n")
        except Exception as e:
            self.log_callback(f"❌ Erro ao salvar hash de anúncio: {str(e)}")

    def _adjust_interval(self, ads_found):
        """Adjusts the interval based on scraping results."""
        if not ads_found:
            self.incomplete_page_count += 1
            if self.incomplete_page_count >= self.incomplete_page_threshold:
                new_interval = min(self.current_interval_minutes * self.interval_multiplier, self.max_interval_minutes)
                if new_interval != self.current_interval_minutes:
                    self.current_interval_minutes = new_interval
                    self.log_callback(f"⏰ Intervalo aumentado para {self.current_interval_minutes} minutos devido a páginas incompletas")
                self.incomplete_page_count = 0
        else:
            self.incomplete_page_count = 0
            if self.current_interval_minutes != self.base_interval_minutes:
                self.current_interval_minutes = self.base_interval_minutes
                self.log_callback(f"⏰ Intervalo restaurado para {self.base_interval_minutes} minuto após sucesso")

    def start(self):
        self.running = True
        self.stop_event.clear() # <--- ADD THIS LINE: Clear the event at the start
        self.log_callback("🚀 Monitoramento iniciado!")
        # self.log_callback(f"📝 Palavras-chave: {', '.join(self.keywords)}")
        # self.log_callback(f"💬 Chat ID: {self.chat_id}")
        # self.log_callback("⏰ Horário de funcionamento: 06:00 - 23:00 (GMT-3)")

        cycle_count = 0

        while self.running: # self.running is set to False by self.stop()
            cycle_start_time = time.time() # Start timing for the full cycle
            
            try:
                # VERIFICAR HORARIO DE FUNCIONAMENTO
                gmt_minus_3 = timezone(timedelta(hours=-3))
                current_time_gmt3 = datetime.now(gmt_minus_3)
                current_hour = current_time_gmt3.hour
                
                self.log_callback(f"🔄 Estado do loop: running={self.running}, hora atual={current_time_gmt3.strftime('%H:%M:%S')}")
                
                if current_hour < 6 or current_hour >= 23:
                    current_time_str = current_time_gmt3.strftime("%H:%M:%S")
                    self.log_callback(f"😴 Fora do horário de funcionamento - {current_time_str} (GMT-3)")
                    self.log_callback("⏰ Próxima verificação será às 06:00")
                    
                    if current_hour >= 23:
                        next_6am = current_time_gmt3.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    else:
                        next_6am = current_time_gmt3.replace(hour=6, minute=0, second=0, microsecond=0)
                    
                    seconds_until_6am = int((next_6am - current_time_gmt3).total_seconds())
                    
                    # --- MODIFIED SLEEP LOGIC ---
                    # Check the stop_event more frequently
                    for i in range(0, seconds_until_6am, 10): # Check every 10 seconds
                        if self.stop_event.is_set(): # <--- Check the event
                            self.running = False # <--- Set running to False to exit main loop
                            self.log_callback("🛑 Loop interrompido durante espera fora do horário por stop_event")
                            break
                        remaining = seconds_until_6am - i
                        hours_remaining = remaining // 3600
                        minutes_remaining = (remaining % 3600) // 60
                        self.log_callback(f"💤 Aguardando horário de funcionamento - {hours_remaining:02d}:{minutes_remaining:02d} restantes")
                        self.stop_event.wait(timeout=10) # <--- Use wait with timeout
        
                    # BREAK if stopped
                    if not self.running: # If break from above loop due to stop_event
                        break
                    continue
                # VERIFICAR HORARIO DE FUNCIONAMENTO

                cycle_count += 1
                current_time = current_time_gmt3.strftime("%H:%M:%S")
                self.log_callback(f"🔍 Verificação #{cycle_count} - {current_time} (GMT-3)")

                # 1.1 - Sortear 4 permutações
                num_permutations_to_use = 1
                # num_permutations_to_use = min(4, len(all_permutations))
                # selected_permutations = random.sample(all_permutations, num_permutations_to_use)
                # self.log_callback(f"🎲 Selecionadas {num_permutations_to_use} permutações de keywords para esta verificação.")

                current_cycle_new_ads = [] # To accumulate ads from all permutations/pages in this cycle

                # 1.2 - Iterar pelas permutações
                # for perm_idx, perm_keywords_tuple in enumerate(selected_permutations):
                first_indexed_perm = (0, tuple(self.keywords))
                for perm_idx,perm_keywords_tuple in [first_indexed_perm]:
                # acima estou evitando permutações para simplificar a tentativa em produção
                
                    perm_keywords = list(perm_keywords_tuple) # Convert tuple to list for consistency
                    # self.log_callback(f"🔄 Processando permutação {perm_idx + 1}/{num_permutations_to_use}: {', '.join(perm_keywords)}")
                    
                    # 2. Iterar por páginas (máximo 3 páginas por permutação)
                    max_pages_per_permutation = 3
                    
                    for page_num in range(1, max_pages_per_permutation + 1):
                        self.log_callback(f"📚 Tentando raspar página {page_num} para a permutação atual...")
                        
                        # 3. Repetir até sucesso, com delays aleatórios
                        page_scrape_success = False
                        page_attempt = 0
                        max_page_attempts = 100 # Max retries for a single page with this permutation
                        while not page_scrape_success and page_attempt < max_page_attempts:
                            if self.stop_event.is_set(): # <--- Check the event here too
                                self.running = False
                                self.log_callback("🛑 Monitoramento interrompido durante raspagem de página por stop_event.")
                                break
                            page_attempt += 1
                            try:
                                self.log_callback(f"🚀 Iniciando scraping da página {page_num} (Tentativa {page_attempt}/{max_page_attempts})")
                                
                                new_ads_from_page = self.scraper.scrape_err(
                                    query_keywords=perm_keywords,
                                    keywords=self.keywords, # Use original keywords for filtering extracted ads
                                    negative_keywords_list=self.negative_keywords_list,
                                    start_page=page_num, # Pass the current page as start_page
                                    num_pages_to_scrape=max_pages_per_permutation,
                                    save_page=False,
                                    page_retry_attempts=1,
                                    page_retry_delay_min=30,
                                    page_retry_delay_max=67
                                )
                                
                                current_cycle_new_ads.extend(new_ads_from_page)
                                page_scrape_success = True
                                self.log_callback(f"✅ Página {page_num} raspada com sucesso para a permutação {perm_idx + 1}. Encontrados {len(new_ads_from_page)} anúncios.")
                                
                            except Exception as e:
                                self.log_callback(f"❌ Erro na raspagem da página {page_num} (Permutação {perm_idx + 1}, Tentativa {page_attempt}/{max_page_attempts}): {type(e).__name__} - {str(e)}")
                                if page_attempt < max_page_attempts:
                                    retry_delay = random.uniform(5, 15) # Random delay between page retries
                                    # --- MODIFIED SLEEP LOGIC ---
                                    if self.stop_event.wait(timeout=retry_delay): # <--- Use wait with timeout
                                        self.running = False
                                        self.log_callback("🛑 Monitoramento interrompido durante espera de retry por stop_event.")
                                        break
                                else:
                                    self.log_callback(f"⚠️ Todas as {max_page_attempts} tentativas falharam para a página {page_num} da permutação {perm_idx + 1}. Prosseguindo para a próxima página/permutação.")
                                    break # Give up on this page, move to next page_num

                        if not page_scrape_success or not self.running: # Check self.running after inner loop breaks
                            self.log_callback(f"⏭️ Pulando para a próxima permutação ou finalizando ciclo, devido a falha persistente na página {page_num} ou parada solicitada.")
                            break # If a page consistently fails, move to next permutation or end

                    # BREAK if stopped
                    if not self.running: # If break from inner page loop due to stop_event
                        break

                # BREAK if stopped
                if not self.running: # If break from permutation loop due to stop_event
                    break

                # Process all collected new ads from the current cycle (all permutations and pages)
                truly_new_ads = []
                truly_new_ads_hash = []
                for ad in current_cycle_new_ads:
                    ad_hash = self._hash_ad(ad)
                    if ad_hash not in self.seen_ads:
                        self.seen_ads.add(ad_hash)
                        truly_new_ads_hash.append(ad_hash)
                        truly_new_ads.append(ad)

                if truly_new_ads:
                    self.log_callback(f"✅ Encontrou {len(truly_new_ads)} anúncios ainda não vistos neste ciclo!")
                    formatted_ads = [f"Título: {ad['title']}\nURL: {ad['url']}" for ad in truly_new_ads]
                    try:
                        messages = self._split_message(formatted_ads)
                        for msg in messages:
                            # BREAK if stopped
                            if not self.running: # <--- Check running flag before sending messages
                                self.log_callback("🛑 Monitoramento interrompido antes de enviar todas as mensagens.")
                                break
                            self.telegram_bot.send_message(self.chat_id, msg)
                            if self.stop_event.wait(timeout=1): # <--- Small delay between sending messages, check for stop
                                self.running = False
                                self.log_callback("🛑 Monitoramento interrompido durante o envio de mensagens.")
                                break
                        if self.running: # Only save if not stopped during message sending
                            for ad_hash in truly_new_ads_hash:
                                self._save_ad_hash(ad_hash)
                    except Exception as e:
                        self.log_callback(f"❌ Erro ao enviar mensagens para Telegram: {str(e)}")
                    if self.running:
                        self.log_callback(f"✅ Enviados {len(truly_new_ads)} novos anúncios para Telegram")
                else:
                    self.log_callback("ℹ️ Nenhum anúncio novo encontrado neste ciclo.")

            except Exception as e:
                self.log_callback(f"❌ Erro geral durante verificação de ciclo: {str(e)}")
                self._adjust_interval(False) # Potentially increase interval on error

            cycle_end_time = time.time() # End timing for the full cycle
            cycle_duration = cycle_end_time - cycle_start_time
            self.log_callback(f"📊 Ciclo de verificação concluído em {cycle_duration:.1f} segundos.")

            # 4. Esperar 30 minutos para o próximo loop que inclua 1.1 a 4
            wait_time_minutes = 30
            self.log_callback(f"⏳ Aguardando próximo ciclo ({wait_time_minutes} minutos)...")
            seconds_to_wait = wait_time_minutes * 60
            
            # --- MODIFIED SLEEP LOGIC ---
            # Use wait() with a short timeout to frequently check the stop_event
            for i in range(0, seconds_to_wait, 10): # Check every 10 seconds
                if self.stop_event.is_set(): # <--- Check the event
                    self.running = False # <--- Set running to False to exit main loop
                    self.log_callback("🛑 Monitoramento interrompido durante espera do ciclo por stop_event.")
                    break
                # Only sleep for the remaining part of the 10-second chunk
                self.stop_event.wait(timeout=10) # <--- Use wait with timeout

        self.log_callback("Monitoramento finalizado.") # <--- Log when the main loop exits

    def _split_message(self, ads):
        messages = []
        for i in range(0, len(ads), self.batch_size):
            batch = ads[i:i + self.batch_size]
            selected_emoji = get_random_emoji()
            message_header = f"{selected_emoji} Novos anúncios encontrados (parte {len(messages) + 1} de {(len(ads) + self.batch_size - 1) // self.batch_size}):\n\n"
            message_content = "\n\n".join(batch)
            messages.append(message_header + message_content)
        return messages

    def stop(self):
        self.running = False
        self.stop_event.set() # <--- ADD THIS LINE: Set the event when stop is called
        self.log_callback("🛑 Comando de parada enviado...")