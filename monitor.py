import threading
import time
from datetime import datetime, timezone, timedelta
import hashlib
import os
from emoji_sorter import get_random_emoji

class Monitor:
    def __init__(self, keywords, negative_keywords_list, scraper, telegram_bot, chat_id, log_callback, hash_file=None, batch_size=20):
        self.keywords = keywords
        self.negative_keywords_list = negative_keywords_list
        self.scraper = scraper
        self.telegram_bot = telegram_bot
        self.chat_id = chat_id
        self.log_callback = log_callback
        self._stop_event = threading.Event() # Use an event for responsive stopping

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
        self.max_pages_per_cycle = 5 # New attribute for scraping multiple pages

    def _hash_ad(self, ad):
        return hashlib.sha256(ad["url"].encode("utf-8")).hexdigest()

    def _load_seen_ads(self):
        seen = set()
        if os.path.exists(self.hash_file):
            try:
                with open(self.hash_file, "r", encoding="utf-8") as f:
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
            with open(self.hash_file, "a", encoding="utf-8") as f:
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
        self.log_callback("🚀 Monitoramento iniciado!")
        self.log_callback(f"📝 Palavras-chave: {", ".join(self.keywords)}")
        self.log_callback(f"💬 Chat ID: {self.chat_id}")
        self.log_callback("⏰ Horário de funcionamento: 06:00 - 23:00 (GMT-3)")
        cycle_count = 0
        while not self._stop_event.is_set(): # Check stop event
            try:
                gmt_minus_3 = timezone(timedelta(hours=-3))
                current_time_gmt3 = datetime.now(gmt_minus_3)
                current_hour = current_time_gmt3.hour
                
                self.log_callback(f"🔄 Estado do loop: running={not self._stop_event.is_set()}, hora atual={current_time_gmt3.strftime("%H:%M:%S")}")
                
                if current_hour < 6 or current_hour >= 23:
                    current_time_str = current_time_gmt3.strftime("%H:%M:%S")
                    self.log_callback(f"😴 Fora do horário de funcionamento - {current_time_str} (GMT-3)")
                    self.log_callback("⏰ Próxima verificação será às 06:00")
                    
                    if current_hour >= 23:
                        next_6am = current_time_gmt3.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    else:
                        next_6am = current_time_gmt3.replace(hour=6, minute=0, second=0, microsecond=0)
                    
                    seconds_until_6am = int((next_6am - current_time_gmt3).total_seconds())
                    
                    # Use wait for responsive sleep
                    self._stop_event.wait(seconds_until_6am)
                    continue

                cycle_count += 1
                current_time = current_time_gmt3.strftime("%H:%M:%S")
                self.log_callback(f"🔍 Verificação #{cycle_count} - {current_time} (GMT-3)")

                # Pass max_pages_per_cycle to scraper
                new_ads = self.scraper.scrape(self.keywords, self.negative_keywords_list, self.max_pages_per_cycle)

                self._adjust_interval(len(new_ads) > 0)

                truly_new_ads = []
                truly_new_ads_hash = []
                for ad in new_ads:
                    ad_hash = self._hash_ad(ad)
                    if ad_hash not in self.seen_ads:
                        self.seen_ads.add(ad_hash)
                        truly_new_ads_hash.append(ad_hash)
                        truly_new_ads.append(ad)

                if truly_new_ads:
                    self.log_callback(f"✅ Encontrou {len(truly_new_ads)} anúncios ainda não vistos")
                    formatted_ads = [f"Título: {ad["title"]}\nURL: {ad["url"]}" for ad in truly_new_ads]
                    try:
                        messages = self._split_message(formatted_ads)
                        for msg in messages:
                            self.telegram_bot.send_message(self.chat_id, msg)
                            # Use wait for responsive sleep
                            self._stop_event.wait(1)
                    except Exception as e:
                        self.log_callback(f"❌ Erro ao enviar mensagens para Telegram: {str(e)}")
                    for ad_hash in truly_new_ads_hash:
                        self._save_ad_hash(ad_hash)
                    self.log_callback(f"✅ Enviados {len(truly_new_ads)} novos anúncios para Telegram")
                else:
                    self.log_callback("ℹ️ Nenhum anúncio novo encontrado")

            except Exception as e:
                self.log_callback(f"❌ Erro durante verificação: {str(e)}")
                self._adjust_interval(False)

            seconds_in_minute = 60
            seconds_to_wait = self.current_interval_minutes * seconds_in_minute

            # Use wait for responsive sleep
            if not self._stop_event.is_set():
                self.log_callback(f"⏳ Aguardando próxima verificação ({self.current_interval_minutes} minutos)...")
                self._stop_event.wait(seconds_to_wait)

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
        self._stop_event.set() # Set the event to signal stopping
        self.log_callback("🛑 Comando de parada enviado...")