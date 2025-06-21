# monitor.py

import threading
import time
from datetime import datetime, timezone, timedelta
import random
import hashlib
import os
from emoji_sorter import get_random_emoji
from itertools import combinations # Apenas combinations é necessário


class Monitor:
    def __init__(self,
        keywords, negative_keywords_list,
        scraper, telegram_bot,
        chat_id, log_callback, hash_file=None,
        monitoring_interval=30,  # Intervalo de monitoramento em minutos
        # batch_size=1 faz receber de 1 em 1 anuncio no telegram.
        batch_size=1, page_depth=3,
        number_set=4,
        retry_attempts=100, min_repeat_time=17,
        max_repeat_time=65,
        allow_subset=False, # Novo parâmetro para ligar/desligar a geração de subconjuntos
        min_subset_size=2, max_subset_size=None # Parâmetros para controle do tamanho do subconjunto
    ):
        self.keywords = keywords
        self.negative_keywords_list = negative_keywords_list
        self.scraper = scraper
        self.telegram_bot = telegram_bot
        self.chat_id = chat_id
        self.log_callback = log_callback
        self.running = False
        self.stop_event = threading.Event()
        self.monitoring_interval = monitoring_interval  # Intervalo de monitoramento em minutos

        # Use home directory for the hash file if not specified
        if hash_file is None:
            data_dir = os.path.join(
                os.path.expanduser("~"), ".marketroxo_data")
            os.makedirs(data_dir, exist_ok=True)
            self.hash_file = os.path.join(data_dir, "seen_ads.txt")
            self.log_callback(f"📁 Using hash file at: {self.hash_file}")
        else:
            self.hash_file = hash_file

        self.batch_size = batch_size
        self.seen_ads = self._load_seen_ads()

        self.page_depth = page_depth
        self.retry_attempts = retry_attempts
        self.min_repeat_time = min_repeat_time
        self.max_repeat_time = max_repeat_time
        self.number_set = number_set

        self.min_subset_size = min_subset_size # Não serão usados
        self.max_subset_size = max_subset_size # Não serão usados
        self.allow_subset = allow_subset # Armazena o novo parâmetro
        self.log_callback(
            f"👹 Allowing keyword subsets: {self.allow_subset} (min: {self.min_subset_size}, max: {self.max_subset_size})")


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
                self.log_callback(
                    f"📂 Carregados {len(seen)} anúncios vistos anteriormente")
            except Exception as e:
                self.log_callback(
                    f"❌ Erro ao carregar anúncios vistos: {str(e)}")
        return seen

    def _save_ad_hash(self, ad_hash):
        try:
            with open(self.hash_file, 'a', encoding='utf-8') as f:
                f.write(f"{ad_hash}\n")
        except Exception as e:
            self.log_callback(f"❌ Erro ao salvar hash de anúncio: {str(e)}")
            

    def _generate_keyword_subsets(self):
        """
        Generates all possible keyword subsets (combinations) based on min/max_subset_size.
        This method is only called if self.allow_subset is True.
        Additionally, it always includes the complete keyword list.
        """
        all_subsets = []
        if self.min_subset_size is None or self.max_subset_size is None:
            self.log_callback("⚠️ min_subset_size ou max_subset_size não definidos corretamente. Gerando apenas o conjunto completo de palavras-chave.")
            return [tuple(self.keywords)]
            
        for i in range(self.min_subset_size, self.max_subset_size + 1):
            if i > len(self.keywords):
                continue
            all_subsets.extend(list(combinations(self.keywords, i)))
            
        full_keywords = tuple(self.keywords)
        if full_keywords not in all_subsets:
            all_subsets.append(full_keywords)
            
        return all_subsets

    def start(self):
        self.running = True
        self.stop_event.clear()
        self.log_callback("🦉 Monitoramento iniciado!")

        cycle_count = 0

        while self.running:
            cycle_start_time = time.time()

            try:
                gmt_minus_3 = timezone(timedelta(hours=-3))
                current_time_gmt3 = datetime.now(gmt_minus_3)
                current_hour = current_time_gmt3.hour

                self.log_callback(
                    f"🔄 Estado do loop: running={self.running}, hora atual={current_time_gmt3.strftime('%H:%M:%S')}")

                if current_hour < 6 or current_hour >= 23:
                    current_time_str = current_time_gmt3.strftime("%H:%M:%S")
                    self.log_callback(
                        f"😴 Fora do horário de funcionamento - {current_time_str} (GMT-3)")
                    self.log_callback("⏰ Próxima verificação será às 06:00")

                    if current_hour >= 23:
                        next_6am = current_time_gmt3.replace(
                            hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    else:
                        next_6am = current_time_gmt3.replace(
                            hour=6, minute=0, second=0, microsecond=0)

                    seconds_until_6am = int(
                        (next_6am - current_time_gmt3).total_seconds())

                    for i in range(0, seconds_until_6am, 10):
                        if self.stop_event.is_set():
                            self.running = False
                            self.log_callback(
                                "🛑 Loop interrompido durante espera fora do horário por stop_event")
                            break
                        remaining = seconds_until_6am - i
                        hours_remaining = remaining // 3600
                        minutes_remaining = (remaining % 3600) // 60
                        self.log_callback(
                            f"💤 Aguardando horário de funcionamento - {hours_remaining:02d}:{minutes_remaining:02d} restantes")
                        self.stop_event.wait(timeout=10)

                    if not self.running:
                        break
                    continue

                cycle_count += 1
                current_time = current_time_gmt3.strftime("%H:%M:%S")
                self.log_callback(
                    f"👓 Verificação #{cycle_count} - {current_time} (GMT-3)")

                selected_keyword_sets = [tuple(self.keywords)]
                # Lógica para decidir quais conjuntos de palavras-chave usar
                if self.allow_subset:
                    all_keyword_subsets = self._generate_keyword_subsets()
                    if not all_keyword_subsets: # Fallback se a geração de subconjuntos retornar vazio (ex: min_subset_size muito alto)
                        self.log_callback("⚠️ Nenhuma combinação de subconjunto gerada com as configurações atuais. Usando palavras-chave originais como fallback.")
                        selected_keyword_sets = [tuple(self.keywords)]
                    else:
                        num_sets_to_use = min(self.number_set, len(all_keyword_subsets)) # Você pode ajustar este número
                        selected_keyword_sets = random.sample(all_keyword_subsets, num_sets_to_use)
                        self.log_callback(f"🎲 Selecionados {num_sets_to_use} subconjuntos de palavras-chave para esta verificação.")

                current_cycle_new_ads = []
                # Iterate through the selected keyword sets
                for set_idx, current_keywords_tuple in enumerate(selected_keyword_sets):
                    # Convert tuple to list for scraper
                    current_keywords = list(current_keywords_tuple)
                    self.log_callback(f"🦭 Processando conjunto de palavras-chave {set_idx + 1}/{len(selected_keyword_sets)}: {', '.join(current_keywords)}")

                    max_pages_per_set = self.page_depth
                    pages_per_scrape = 1
                    number_retry_scrape = 1

                    for page_num in range(1, max_pages_per_set + 1):
                        self.log_callback(
                            f"📚 Tentando raspar página {page_num} para o conjunto de palavras chave atual...")

                        page_scrape_success = False
                        page_attempt = 0
                        max_page_attempts = self.retry_attempts
                        while not page_scrape_success and page_attempt < max_page_attempts:
                            if self.stop_event.is_set():
                                self.running = False
                                self.log_callback(
                                    "🛑 Monitoramento interrompido durante raspagem de página por stop_event.")
                                break
                            page_attempt += 1
                            try:
                                self.log_callback(
                                    f"🪜 Inicio processo monitor de scrape da página {page_num} (Tentativa {page_attempt}/{max_page_attempts})")

                                new_ads_from_page = self.scraper.scrape_err(
                                    query_keywords=current_keywords, # Use o conjunto de palavras-chave atual
                                    keywords=self.keywords,  # Use as palavras-chave originais para filtrar anúncios extraídos (se scraper usar)
                                    negative_keywords_list=self.negative_keywords_list,
                                    start_page=page_num,
                                    save_page=False,
                                    num_pages_to_scrape=pages_per_scrape,
                                    page_retry_attempts=number_retry_scrape,
                                    page_retry_delay_min=self.min_repeat_time,
                                    page_retry_delay_max=self.max_repeat_time
                                )

                                current_cycle_new_ads.extend(new_ads_from_page)
                                page_scrape_success = True
                                self.log_callback(
                                    f"🏆 Página {page_num} raspada com sucesso para o conjunto {set_idx + 1}. Encontrados {len(new_ads_from_page)} anúncios.")

                            except Exception as e:
                                self.log_callback(
                                    f"❌ Erro na raspagem da página {page_num} (Conjunto {set_idx + 1}, Tentativa {page_attempt}/{max_page_attempts}): {type(e).__name__} - {str(e)}")
                                if page_attempt < max_page_attempts:
                                    retry_delay = random.uniform(5, 15)
                                    if self.stop_event.wait(timeout=retry_delay):
                                        self.running = False
                                        self.log_callback(
                                            "🛑 Monitoramento interrompido durante espera de retry por stop_event.")
                                        break
                                else:
                                    self.log_callback(
                                        f"⚠️ Todas as {max_page_attempts} tentativas falharam para a página {page_num} do conjunto {set_idx + 1}. Prosseguindo para a próxima página/conjunto.")
                                    break

                        if not page_scrape_success or not self.running:
                            self.log_callback(
                                f"⏭️ Pulando para o próximo conjunto ou finalizando ciclo, devido a falha persistente na página {page_num} ou parada solicitada.")
                            break

                    if not self.running:
                        break

                if not self.running:
                    break

                # Cria uma lista de tuplas (hash, ad) para todos os anúncios do ciclo atual
                hash_ad_tuples = [(self._hash_ad(ad), ad) for ad in current_cycle_new_ads]
                truly_new_ads = []
                truly_new_ads_hash = []
                for ad_hash, ad in hash_ad_tuples:
                    # Verifica se o anúncio já foi visto anteriormente
                    if ad_hash in self.seen_ads:
                        continue
                    # Verifica se o mesmo anúncio (baseado no hash) já está sendo considerado neste ciclo
                    if ad_hash in truly_new_ads_hash:
                        continue
                    # Se o anúncio é novo, adiciona-o à lista e marca como visto
                    truly_new_ads_hash.append(ad_hash)
                    truly_new_ads.append(ad)
                    # self.seen_ads.add(ad_hash)

                if truly_new_ads:
                    self.log_callback(
                        f"🍻 Encontrou {len(truly_new_ads)} anúncios ainda não vistos neste ciclo!")
                    formatted_ads = [
                        f"Título: {ad['title']}\nURL: {ad['url']}" for ad in truly_new_ads]
                    try:
                        messages = self._split_message(formatted_ads)
                        for msg in messages:
                            if not self.running:
                                self.log_callback(
                                    "🛑 Monitoramento interrompido antes de enviar todas as mensagens.")
                                break
                            self.telegram_bot.send_message(self.chat_id, msg)
                            if self.stop_event.wait(timeout=1):
                                self.running = False
                                self.log_callback(
                                    "🛑 Monitoramento interrompido durante o envio de mensagens.")
                                break
                        if self.running:
                            for ad_hash in truly_new_ads_hash:
                                self._save_ad_hash(ad_hash)
                    except Exception as e:
                        self.log_callback(
                            f"❌ Erro ao enviar mensagens para Telegram: {str(e)}")
                    if self.running:
                        self.log_callback(
                            f"📩 Enviados {len(truly_new_ads)} novos anúncios para Telegram")
                else:
                    self.log_callback(
                        "ℹ️ Nenhum anúncio novo encontrado neste ciclo.")

            except Exception as e:
                self.log_callback(
                    f"❌ Erro geral durante verificação de ciclo: {str(e)}")

            cycle_end_time = time.time()
            cycle_duration = cycle_end_time - cycle_start_time
            self.log_callback(
                f"⏱️ Ciclo de verificação concluído em {cycle_duration:.1f} segundos.")

            wait_time_minutes = self.monitoring_interval
            self.log_callback(
                f"⏳ Aguardando próximo ciclo ({wait_time_minutes} minutos)...")
            seconds_to_wait = wait_time_minutes * 60

            for i in range(0, seconds_to_wait, 10):
                if self.stop_event.is_set():
                    self.running = False
                    self.log_callback(
                        "🛑 Monitoramento interrompido durante espera do ciclo por stop_event.")
                    break
                self.stop_event.wait(timeout=10)

        self.log_callback("Monitoramento finalizado.")

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

    def stop(self):
        self.running = False
        self.stop_event.set()
        self.log_callback("🛑 Comando de parada enviado...")