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
        
        self.log_callback(f"😴 Fora do horário de funcionamento - {current_time_str} (GMT-3)")
        self.log_callback("⏰ Próxima verificação será às 06:00")

        if current_hour >= 23:
            next_6am = current_time_gmt3.replace(
                hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_6am = current_time_gmt3.replace(
                hour=6, minute=0, second=0, microsecond=0)

        seconds_until_6am = int((next_6am - current_time_gmt3).total_seconds())

        for i in range(0, seconds_until_6am, 10):
            if self.stop_event.is_set():
                self.running = False
                self.log_callback("🛑 Loop interrompido durante espera fora do horário por stop_event")
                return False
            
            remaining = seconds_until_6am - i
            hours_remaining = remaining // 3600
            minutes_remaining = (remaining % 3600) // 60
            self.log_callback(f"💤 Aguardando horário de funcionamento - {hours_remaining:02d}:{minutes_remaining:02d} restantes")
            self.stop_event.wait(timeout=10)
        
        return True

    def _select_keyword_sets(self):
        """Seleciona os conjuntos de palavras-chave para usar no ciclo atual"""
        selected_keyword_sets = [tuple(self.keywords)]
        
        if self.allow_subset:
            all_keyword_subsets = self._generate_keyword_subsets()
            if not all_keyword_subsets:
                self.log_callback("⚠️ Nenhuma combinação de subconjunto gerada com as configurações atuais. Usando palavras-chave originais como fallback.")
                selected_keyword_sets = [tuple(self.keywords)]
            else:
                num_sets_to_use = min(self.number_set, len(all_keyword_subsets))
                selected_keyword_sets = random.sample(all_keyword_subsets, num_sets_to_use)
                self.log_callback(f"🎲 Selecionados {num_sets_to_use} subconjuntos de palavras-chave para esta verificação.")
        
        return selected_keyword_sets

    def _scrape_page(self, page_num, current_keywords, set_idx, total_sets):
        """Raspa uma página específica com tentativas de retry"""
        self.log_callback(f"📚 Tentando raspar página {page_num}/{self.page_depth} para o conjunto de palavras chave atual..., conjunto: {set_idx + 1}/{total_sets}.")
        
        page_attempt = 0
        while page_attempt < self.retry_attempts:
            if self.stop_event.is_set():
                self.running = False
                self.log_callback("🛑 Monitoramento interrompido durante raspagem de página por stop_event.")
                return None
            
            page_attempt += 1
            try:
                self.log_callback(f"🪜 Inicio processo monitor de scrape da página {page_num} (Tentativa {page_attempt}/{self.retry_attempts})")

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

                self.log_callback(f"🏆 Página {page_num} raspada com sucesso para o conjunto {set_idx + 1}. Encontrados {len(new_ads_from_page)} anúncios.")
                return new_ads_from_page

            except Exception as e:
                self.log_callback(f"❌ Erro na raspagem da página {page_num} (Conjunto {set_idx + 1}, Tentativa {page_attempt}/{self.retry_attempts}): {type(e).__name__} - {str(e)}")
                
                if page_attempt < self.retry_attempts:
                    retry_delay = random.uniform(5, 15)
                    if self.stop_event.wait(timeout=retry_delay):
                        self.running = False
                        self.log_callback("🛑 Monitoramento interrompido durante espera de retry por stop_event.")
                        return None
                else:
                    self.log_callback(f"⚠️ Todas as {self.retry_attempts} tentativas falharam para a página {page_num} do conjunto {set_idx + 1}. Prosseguindo para a próxima página/conjunto.")
                    return None
        
        return None

    def _scrape_keyword_set(self, current_keywords_tuple, set_idx, total_sets):
        """Raspa todas as páginas para um conjunto específico de palavras-chave"""
        current_keywords = list(current_keywords_tuple)
        self.log_callback(f"🦭 Processando conjunto de palavras-chave {set_idx + 1}/{total_sets}: {', '.join(current_keywords)}")
        
        ads_from_set = []
        
        for page_num in range(1, self.page_depth + 1):
            new_ads_from_page = self._scrape_page(page_num, current_keywords, set_idx, total_sets)
            
            if new_ads_from_page is None:
                self.log_callback(f"⏭️ Pulando para o próximo conjunto devido a falha persistente na página {page_num}.")
                break
            
            ads_from_set.extend(new_ads_from_page)
            
            if not self.running:
                break
        
        return ads_from_set

    def _process_new_ads(self, all_ads):
        """Processa anúncios encontrados, filtra duplicatas e retorna anúncios realmente novos"""
        hash_ad_tuples = [(self._hash_ad(ad), ad) for ad in all_ads]
        truly_new_ads = []
        truly_new_ads_hash_set = set()  # Usar set para garantir unicidade
        truly_new_ads_hash_list = []    # Lista para manter ordem
        
        for ad_hash, ad in hash_ad_tuples:
            # Verifica se o anúncio já foi visto anteriormente
            if ad_hash in self.seen_ads:
                continue
            # Verifica se o mesmo anúncio (baseado no hash) já está sendo considerado neste ciclo
            if ad_hash in truly_new_ads_hash_set:
                continue
            # Se o anúncio é novo, adiciona-o à lista
            truly_new_ads_hash_set.add(ad_hash)
            truly_new_ads_hash_list.append(ad_hash)
            truly_new_ads.append(ad)
        
        return truly_new_ads, truly_new_ads_hash_list

    def _send_new_ads_to_telegram(self, truly_new_ads, truly_new_ads_hash):
        """Envia anúncios novos para o Telegram e salva os hashes"""
        if not truly_new_ads:
            self.log_callback("ℹ️ Nenhum anúncio novo encontrado neste ciclo.")
            return
        
        self.log_callback(f"🍻 Encontrou {len(truly_new_ads)} anúncios ainda não vistos neste ciclo!")
        
        # Formatação com hash incluído
        formatted_ads = []
        for i, ad in enumerate(truly_new_ads):
            ad_hash = truly_new_ads_hash[i]
            formatted_ad = f"Título: {ad['title']}\nURL: {ad['url']}\nHash: {ad_hash[:8]}...{ad_hash[-8:]}"
            formatted_ads.append(formatted_ad)
        
        try:
            messages = self._split_message(formatted_ads)
            for msg in messages:
                if not self.running:
                    self.log_callback("🛑 Monitoramento interrompido antes de enviar todas as mensagens.")
                    break
                
                self.telegram_bot.send_message(self.chat_id, msg)
                
                if self.stop_event.wait(timeout=1):
                    self.running = False
                    self.log_callback("🛑 Monitoramento interrompido durante o envio de mensagens.")
                    break
            
            if self.running:
                # Adicionar hashes ao conjunto de vistos E salvar no arquivo
                for ad_hash in truly_new_ads_hash:
                    self.seen_ads.add(ad_hash)  # Adiciona ao set em memória
                    self._save_ad_hash(ad_hash)  # Salva no arquivo
                self.log_callback(f"📩 Enviados {len(truly_new_ads)} novos anúncios para Telegram")
                
        except Exception as e:
            self.log_callback(f"❌ Erro ao enviar mensagens para Telegram: {str(e)}")

    def _wait_for_next_cycle(self):
        """Aguarda o intervalo antes do próximo ciclo de monitoramento"""
        wait_time_minutes = self.monitoring_interval
        self.log_callback(f"⏳ Aguardando próximo ciclo ({wait_time_minutes} minutos)...")
        seconds_to_wait = wait_time_minutes * 60

        for i in range(0, seconds_to_wait, 10):
            if self.stop_event.is_set():
                self.running = False
                self.log_callback("🛑 Monitoramento interrompido durante espera do ciclo por stop_event.")
                return False
            self.stop_event.wait(timeout=10)
        
        return True

    def _run_monitoring_cycle(self, cycle_count):
        """Executa um ciclo completo de monitoramento"""
        cycle_start_time = time.time()
        
        try:
            # Verificar horário de funcionamento
            within_hours, current_time_gmt3 = self._is_within_operating_hours()
            
            self.log_callback(f"🔄 Estado do loop: running={self.running}, hora atual={current_time_gmt3.strftime('%H:%M:%S')}")
            
            if not within_hours:
                return self._wait_for_operating_hours(current_time_gmt3)
            
            # Log do início do ciclo
            current_time = current_time_gmt3.strftime("%H:%M:%S")
            self.log_callback(f"👓 Verificação #{cycle_count} - {current_time} (GMT-3)")
            
            # Selecionar conjuntos de palavras-chave
            selected_keyword_sets = self._select_keyword_sets()
            
            # Raspar anúncios para todos os conjuntos de palavras-chave
            current_cycle_new_ads = []
            for set_idx, current_keywords_tuple in enumerate(selected_keyword_sets):
                ads_from_set = self._scrape_keyword_set(current_keywords_tuple, set_idx, len(selected_keyword_sets))
                current_cycle_new_ads.extend(ads_from_set)
                
                if not self.running:
                    break
            
            if not self.running:
                return False
            
            # Processar anúncios novos
            truly_new_ads, truly_new_ads_hash = self._process_new_ads(current_cycle_new_ads)
            
            # Enviar para Telegram
            self._send_new_ads_to_telegram(truly_new_ads, truly_new_ads_hash)
            
        except Exception as e:
            self.log_callback(f"❌ Erro geral durante verificação de ciclo: {str(e)}")
        
        # Log do fim do ciclo
        cycle_end_time = time.time()
        cycle_duration = cycle_end_time - cycle_start_time
        self.log_callback(f"⏱️ Ciclo de verificação concluído em {cycle_duration:.1f} segundos.")
        
        return True

    def start(self):
        """Função principal do monitoramento - agora muito mais limpa!"""
        self.running = True
        self.stop_event.clear()
        self.log_callback("🦉 Monitoramento iniciado!")

        cycle_count = 0

        while self.running:
            cycle_count += 1
            
            # Executa um ciclo completo de monitoramento
            if not self._run_monitoring_cycle(cycle_count):
                break
            
            # Aguarda o próximo ciclo
            if not self._wait_for_next_cycle():
                break

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