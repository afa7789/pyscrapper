import threading
import time
from datetime import datetime, timezone, timedelta
import random
import hashlib
import os
from emoji_sorter import get_random_emoji
from itertools import combinations
from logging_config import get_logger
from request_stats import RequestStats


class Monitor:
    def __init__(self,
                 keywords, negative_keywords_list,
                 scraper, telegram_bot,
                 chat_id, hash_file=None,
                 monitoring_interval=30,
                 batch_size=1, page_depth=3,
                 number_set=4,
                 retry_attempts=100, min_repeat_time=17,
                 max_repeat_time=65,
                 allow_subset=False,
                 min_subset_size=2, max_subset_size=None,
                 stats_file=None, max_history=1000,
                 send_as_batch=True
                 ):
        self.keywords = keywords
        self.negative_keywords_list = negative_keywords_list
        self.scraper = scraper
        self.telegram_bot = telegram_bot
        self.chat_id = chat_id
        self.logger = get_logger()
        self.is_running = False
        self.stop_event = threading.Event()
        self.monitoring_interval = monitoring_interval
        self.thread = None

        # Inicializa sistema de estatísticas
        self.stats = RequestStats(stats_file=stats_file, max_history=max_history)

        # Use home directory for the hash file if not specified
        if hash_file is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".marketroxo_data")
            os.makedirs(data_dir, exist_ok=True)
            self.hash_file = os.path.join(data_dir, "seen_ads.txt")
            self.logger.info(f"📁 Using hash file at: {self.hash_file}")
        else:
            self.hash_file = hash_file

        self.batch_size = batch_size
        self.seen_ads = self._load_seen_ads()

        self.send_as_batch = send_as_batch

        self.page_depth = page_depth
        self.retry_attempts = retry_attempts
        self.min_repeat_time = min_repeat_time
        self.max_repeat_time = max_repeat_time
        self.number_set = number_set

        self.min_subset_size = min_subset_size
        self.max_subset_size = max_subset_size
        self.allow_subset = allow_subset
        self.logger.info(f"👹 Allowing keyword subsets: {self.allow_subset} (min: {self.min_subset_size}, max: {self.max_subset_size})")

    def get_health_stats(self):
        """Retorna estatísticas para endpoint /health"""
        return self.stats.get_stats_summary()

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
                self.logger.info(f"📂 Carregados {len(seen)} anúncios vistos anteriormente")
            except Exception as e:
                self.logger.error(f"❌ Erro ao carregar anúncios vistos: {str(e)}")
        return seen

    def _save_ad_hash(self, ad_hash):
        """Salva hash no arquivo com verificação de duplicata"""
        try:
            if os.path.exists(self.hash_file):
                with open(self.hash_file, 'r', encoding='utf-8') as f:
                    existing_hashes = {line.strip() for line in f if line.strip()}
                if ad_hash in existing_hashes:
                    self.logger.info(f"🔄 Hash {ad_hash[:8]}...{ad_hash[-8:]} já existe no arquivo - não salvando novamente")
                    return
            
            with open(self.hash_file, 'a', encoding='utf-8') as f:
                f.write(f"{ad_hash}\n")
        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar hash de anúncio: {str(e)}")

    def _generate_keyword_subsets(self):
        """Generates all possible keyword subsets based on min/max_subset_size."""
        all_subsets = []
        if self.min_subset_size is None or self.max_subset_size is None:
            self.logger.warning("⚠️ min_subset_size ou max_subset_size não definidos corretamente. Gerando apenas o conjunto completo de palavras-chave.")
            return [tuple(self.keywords)]
            
        for i in range(self.min_subset_size, self.max_subset_size + 1):
            if i > len(self.keywords):
                continue
            all_subsets.extend(list(combinations(self.keywords, i)))
            
        full_keywords = tuple(self.keywords)
        if full_keywords not in all_subsets:
            all_subsets.append(full_keywords)
            
        return all_subsets

    def _is_within_operating_hours(self):
        """Verifica se está dentro do horário de funcionamento (6h-23h GMT-3)"""
        gmt_minus_3 = timezone(timedelta(hours=-3))
        current_time_gmt3 = datetime.now(gmt_minus_3)
        current_hour = current_time_gmt3.hour
        return 6 <= current_hour < 23, current_time_gmt3

    def _wait_for_operating_hours(self, current_time_gmt3):
        """Aguarda até o próximo horário de funcionamento (6h)"""
        current_hour = current_time_gmt3.hour
        current_time_str = current_time_gmt3.strftime("%H:%M:%S")
        
        self.logger.info(f"😴 Fora do horário de funcionamento - {current_time_str} (GMT-3)")
        self.logger.info("⏰ Próxima verificação será às 06:00")

        if current_hour >= 23:
            next_6am = current_time_gmt3.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_6am = current_time_gmt3.replace(hour=6, minute=0, second=0, microsecond=0)

        seconds_until_6am = int((next_6am - current_time_gmt3).total_seconds())

        for i in range(0, seconds_until_6am, 10):
            if self.stop_event.is_set():
                self.is_running = False
                self.logger.info("🛑 Loop interrompido durante espera fora do horário por stop_event")
                return False
            
            remaining = seconds_until_6am - i
            hours_remaining = remaining // 3600
            minutes_remaining = (remaining % 3600) // 60
            self.logger.info(f"💤 Aguardando horário de funcionamento - {hours_remaining:02d}:{minutes_remaining:02d} restantes")
            self.stop_event.wait(timeout=10)
        
        return True

    def _select_keyword_sets(self):
        """Seleciona os conjuntos de palavras-chave para usar no ciclo atual"""
        selected_keyword_sets = [tuple(self.keywords)]
        
        if self.allow_subset:
            all_keyword_subsets = self._generate_keyword_subsets()
            if not all_keyword_subsets:
                self.logger.warning("⚠️ Nenhuma combinação de subconjunto gerada com as configurações atuais. Usando palavras-chave originais como fallback.")
                selected_keyword_sets = [tuple(self.keywords)]
            else:
                num_sets_to_use = min(self.number_set, len(all_keyword_subsets))
                selected_keyword_sets = random.sample(all_keyword_subsets, num_sets_to_use)
                self.logger.info(f"🎲 Selecionados {num_sets_to_use} subconjuntos de palavras-chave para esta verificação.")
        
        return selected_keyword_sets

    def _scrape_page(self, page_num, current_keywords, set_idx, total_sets):
        """Raspa uma página específica com tentativas de retry"""
        self.logger.info(f"📚 Tentando raspar página {page_num}/{self.page_depth} para o conjunto de palavras chave atual..., conjunto: {set_idx + 1}/{total_sets}.")
        
        page_attempt = 0
        while page_attempt < self.retry_attempts:
            if self.stop_event.is_set():
                self.is_running = False
                self.logger.info("🛑 Monitoramento interrompido durante raspagem de página por stop_event.")
                return None
            
            page_attempt += 1
            try:
                self.logger.info(f"🪜 Inicio processo monitor de scrape da página {page_num} (Tentativa {page_attempt}/{self.retry_attempts})")

                new_ads_from_page = self.scraper.scrape_err(
                    query_keywords=current_keywords,
                    keywords=self.keywords,
                    negative_keywords_list=self.negative_keywords_list,
                    start_page=page_num,
                    save_page=False,
                    num_pages_to_scrape=1,
                    page_retry_attempts=1,
                    page_retry_delay_min=self.min_repeat_time,
                    page_retry_delay_max=self.max_repeat_time
                )

                # Registra sucesso
                self.stats.record_success(
                    keywords=current_keywords,
                    page_num=page_num,
                    ads_found=len(new_ads_from_page)
                )

                self.logger.info(f"🏆 Página {page_num} raspada com sucesso para o conjunto {set_idx + 1}. Encontrados {len(new_ads_from_page)} anúncios.")
                return new_ads_from_page

            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
                
                # Registra erro
                self.stats.record_error(
                    keywords=current_keywords,
                    page_num=page_num,
                    error_type=error_type,
                    error_message=error_message
                )
                
                self.logger.error(f"❌ Erro na raspagem da página {page_num} (Conjunto {set_idx + 1}, Tentativa {page_attempt}/{self.retry_attempts}): {error_type} - {error_message}")
                
                if page_attempt < self.retry_attempts:
                    retry_delay = random.uniform(5, 15)
                    if self.stop_event.wait(timeout=retry_delay):
                        self.is_running = False
                        self.logger.info("🛑 Monitoramento interrompido durante espera de retry por stop_event.")
                        return None
                else:
                    self.logger.warning(f"⚠️ Todas as {self.retry_attempts} tentativas falharam para a página {page_num} do conjunto {set_idx + 1}. Prosseguindo para a próxima página/conjunto.")
                    return None
        
        return None

    def _scrape_keyword_set(self, current_keywords_tuple, set_idx, total_sets):
        """Raspa todas as páginas para um conjunto específico de palavras-chave"""
        current_keywords = list(current_keywords_tuple)
        self.logger.info(f"🦭 Processando conjunto de palavras-chave {set_idx + 1}/{total_sets}: {', '.join(current_keywords)}")
        
        ads_from_set = []
        
        for page_num in range(1, self.page_depth + 1):
            new_ads_from_page = self._scrape_page(page_num, current_keywords, set_idx, total_sets)
            
            if new_ads_from_page is None:
                self.logger.info(f"⏭️ Pulando para o próximo conjunto devido a falha persistente na página {page_num}.")
                break
            
            ads_from_set.extend(new_ads_from_page)
            
            if not self.is_running:
                break
        
        return ads_from_set

    def _process_new_ads(self, all_ads):
        """Processa anúncios encontrados, filtra duplicatas e retorna anúncios realmente novos"""
        hash_ad_tuples = [(self._hash_ad(ad), ad) for ad in all_ads]
        truly_new_ads = []
        truly_new_ads_hash_list = []
        seen_in_this_cycle = set()
        
        for ad_hash, ad in hash_ad_tuples:
            if ad_hash in self.seen_ads:
                continue
            if ad_hash in seen_in_this_cycle:
                self.logger.info(f"🔄 Hash duplicado encontrado no mesmo ciclo: {ad_hash[:8]}...{ad_hash[-8:]} - Ignorando")
                continue
            
            seen_in_this_cycle.add(ad_hash)
            truly_new_ads_hash_list.append(ad_hash)
            truly_new_ads.append(ad)
        
        return truly_new_ads, truly_new_ads_hash_list

    def _send_new_ads_to_telegram(self, truly_new_ads, truly_new_ads_hash):
        """Envia anúncios novos para o Telegram e salva os hashes"""
        if not truly_new_ads:
            self.logger.info("ℹ️ Nenhum anúncio novo encontrado neste ciclo.")
            return
        
        self.logger.info(f"🍻 Encontrou {len(truly_new_ads)} anúncios ainda não vistos neste ciclo!")
        
        unique_hashes = set(truly_new_ads_hash)
        if len(unique_hashes) != len(truly_new_ads_hash):
            self.logger.warning(f"⚠️ AVISO: Detectadas {len(truly_new_ads_hash) - len(unique_hashes)} duplicatas nos hashes antes do envio!")
            seen_hashes = set()
            filtered_ads = []
            filtered_hashes = []
            for i, ad_hash in enumerate(truly_new_ads_hash):
                if ad_hash not in seen_hashes:
                    seen_hashes.add(ad_hash)
                    filtered_ads.append(truly_new_ads[i])
                    filtered_hashes.append(ad_hash)
            truly_new_ads = filtered_ads
            truly_new_ads_hash = filtered_hashes
            self.logger.info(f"🔧 Após filtrar duplicatas: {len(truly_new_ads)} anúncios únicos")
        
        formatted_ads = []
        for i, ad in enumerate(truly_new_ads):
            ad_hash = truly_new_ads_hash[i]
            if ad_hash in self.seen_ads:
                self.logger.info(f"🚫 Hash {ad_hash[:8]}...{ad_hash[-8:]} já foi visto - pulando envio")
                continue
            formatted_ad = f"Título: {ad['title']}\nURL: {ad['url']}\nHash: {ad_hash[:8]}...{ad_hash[-8:]}"
            formatted_ads.append(formatted_ad)
        
        if not formatted_ads:
            self.logger.info("ℹ️ Nenhum anúncio válido restou após verificações de duplicata.")
            return
        
        try:
            messages = self._split_message(formatted_ads)
            successfully_sent_count = 0
            
            for msg_idx, msg in enumerate(messages):
                if not self.is_running:
                    self.logger.info("🛑 Monitoramento interrompido antes de enviar todas as mensagens.")
                    break
                
                try:
                    self.telegram_bot.send_message(self.chat_id, msg)
                    successfully_sent_count += len(formatted_ads[msg_idx * self.batch_size:(msg_idx + 1) * self.batch_size])
                    self.logger.info(f"📤 Mensagem {msg_idx + 1}/{len(messages)} enviada com sucesso")
                except Exception as send_error:
                    self.logger.error(f"❌ Erro ao enviar mensagem {msg_idx + 1}/{len(messages)}: {str(send_error)}")
                    continue
                
                if self.stop_event.wait(timeout=1):
                    self.is_running = False
                    self.logger.info("🛑 Monitoramento interrompido durante o envio de mensagens.")
                    break
            
            if self.is_running and successfully_sent_count > 0:
                hashes_to_save = truly_new_ads_hash[:successfully_sent_count]
                for ad_hash in hashes_to_save:
                    if ad_hash not in self.seen_ads:
                        self.seen_ads.add(ad_hash)
                        self._save_ad_hash(ad_hash)
                self.logger.info(f"📩 Enviados {successfully_sent_count} novos anúncios para Telegram e salvos {len(hashes_to_save)} hashes")
                
        except Exception as e:
            self.logger.error(f"❌ Erro geral ao enviar mensagens para Telegram: {str(e)}")

    def _wait_for_next_cycle(self):
        """Aguarda o intervalo antes do próximo ciclo de monitoramento"""
        wait_time_minutes = self.monitoring_interval
        self.logger.info(f"⏳ Aguardando próximo ciclo ({wait_time_minutes} minutos)...")
        seconds_to_wait = wait_time_minutes * 60

        for i in range(0, seconds_to_wait, 10):
            if self.stop_event.is_set():
                self.is_running = False
                self.logger.info("🛑 Monitoramento interrompido durante espera do ciclo por stop_event.")
                return False
            self.stop_event.wait(timeout=10)
        
        return True

    def _run_monitoring_cycle(self, cycle_count):
        """Executa um ciclo completo de monitoramento"""
        cycle_start_time = time.time()
        
        try:
            within_hours, current_time_gmt3 = self._is_within_operating_hours()
            
            self.logger.info(f"🔄 Estado do loop: running={self.is_running}, hora atual={current_time_gmt3.strftime('%H:%M:%S')}")
            
            if not within_hours:
                return self._wait_for_operating_hours(current_time_gmt3)
            
            current_time = current_time_gmt3.strftime("%H:%M:%S")
            self.logger.info(f"👓 Verificação #{cycle_count} - {current_time} (GMT-3)")
            
            selected_keyword_sets = self._select_keyword_sets()
            
            if self.send_as_batch :
                current_cycle_new_ads = []
                for set_idx, current_keywords_tuple in enumerate(selected_keyword_sets):
                    ads_from_set = self._scrape_keyword_set(current_keywords_tuple, set_idx, len(selected_keyword_sets))
                    current_cycle_new_ads.extend(ads_from_set)
                    
                    if not self.is_running:
                        break
                
                if not self.is_running:
                    return False
                
                truly_new_ads, truly_new_ads_hash = self._process_new_ads(current_cycle_new_ads)
                
                self._send_new_ads_to_telegram(truly_new_ads, truly_new_ads_hash)
            else:
                for set_idx, current_keywords_tuple in enumerate(selected_keyword_sets):
                    ads_from_set = self._scrape_keyword_set(current_keywords_tuple, set_idx, len(selected_keyword_sets))
                    
                    if not ads_from_set:
                        continue
                    
                    truly_new_ads, truly_new_ads_hash = self._process_new_ads(ads_from_set)
                    
                    if truly_new_ads:
                        self._send_new_ads_to_telegram(truly_new_ads, truly_new_ads_hash)
        except Exception as e:
            self.logger.error(f"❌ Erro geral durante verificação de ciclo: {str(e)}")
        
        cycle_end_time = time.time()
        cycle_duration = cycle_end_time - cycle_start_time
        self.logger.info(f"⏱️ Ciclo de verificação concluído em {cycle_duration:.1f} segundos.")
        
        return True

    def start(self):
        """Função principal do monitoramento (síncrona)"""
        self.is_running = True
        self.stop_event.clear()
        self.logger.info("🦉 Monitoramento iniciado!")

        cycle_count = 0

        while self.is_running:
            cycle_count += 1
            
            if not self._run_monitoring_cycle(cycle_count):
                break
            
            if not self._wait_for_next_cycle():
                break

        self.is_running = False
        self.logger.info("Monitoramento finalizado.")

    def start_async(self):
        """Inicia o monitoramento em uma thread separada"""
        if self.is_running:
            self.logger.warning("Tentativa de iniciar monitoramento já ativo")
            return False
        self.thread = threading.Thread(target=self.start, daemon=True)
        self.thread.start()
        self.logger.info("Monitoramento iniciado em thread separada")
        return True

    def stop(self):
        """Para o monitoramento e retorna se foi bem-sucedido"""
        if not self.is_running:
            self.logger.info("Monitoramento já está parado")
            return True
        
        self.logger.info("🛑 Comando de parada enviado...")
        self.stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                self.logger.warning("Monitoramento não terminou completamente após timeout")
                return False
        
        self.is_running = False
        self.thread = None
        self.logger.info("Monitoramento parado com sucesso")
        return True

    def _split_message(self, ads):
        messages = []
        for i in range(0, len(ads), self.batch_size):
            batch = ads[i:i + self.batch_size]
            selected_emoji = get_random_emoji()
            if self.batch_size == 1:
                message_header = f"{selected_emoji} Novo anúncio encontrado:\n\n"
            else:
                message_header = f"{selected_emoji} Novos anúncios encontrados (parte {len(messages) + 1} de {(len(ads) + self.batch_size - 1) // self.batch_size}):\n\n"
            message_content = "\n\n".join(batch)
            messages.append(message_header + message_content)
        return messages