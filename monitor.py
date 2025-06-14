import threading
import time
from datetime import datetime
import hashlib
import os

# in the future scraper can be multiple scrapers


class Monitor:
    def __init__(self, keywords, negative_keywords_list, scraper, telegram_bot, chat_id, log_callback, hash_file=None, batch_size=20):
        self.keywords = keywords
        self.negative_keywords_list = negative_keywords_list
        self.scraper = scraper
        self.telegram_bot = telegram_bot
        self.chat_id = chat_id
        self.log_callback = log_callback
        self.running = False

        # Use home directory for the hash file if not specified
        if hash_file is None:
            # Create a directory for our application data in the user's home directory
            data_dir = os.path.join(
                os.path.expanduser("~"), ".marketroxo_data")
            os.makedirs(data_dir, exist_ok=True)
            self.hash_file = os.path.join(data_dir, "seen_ads.txt")
            self.log_callback(f"📁 Using hash file at: {self.hash_file}")
        else:
            self.hash_file = hash_file

        self.batch_size = batch_size
        self.seen_ads = self._load_seen_ads()  # Load previously seen ads from file

    def _hash_ad(self, ad):
        """Create a hash of the ad URL"""
        return hashlib.sha256(ad['url'].encode('utf-8')).hexdigest()

    def _load_seen_ads(self):
        """Load previously seen ad hashes from file"""
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
        """Save a hash to the seen ads file"""
        try:
            with open(self.hash_file, 'a', encoding='utf-8') as f:
                f.write(f"{ad_hash}\n")
        except Exception as e:
            self.log_callback(f"❌ Erro ao salvar hash de anúncio: {str(e)}")

    def start(self):
        """Starts the monitoring loop."""
        self.running = True
        self.log_callback("🚀 Monitoramento iniciado!")
        self.log_callback(f"📝 Palavras-chave: {', '.join(self.keywords)}")
        self.log_callback(f"💬 Chat ID: {self.chat_id}")
        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                current_time = datetime.now().strftime("%H:%M:%S")
                self.log_callback(
                    f"🔍 Verificação #{cycle_count} - {current_time}")

                #  when we add multiple scrapers, we can loop through them
                #  and scrape each adding the results to new_ads
                new_ads = self.scraper.scrape(
                    self.keywords, self.negative_keywords_list, 1)

                # Filter out already seen ads using hashes
                truly_new_ads = []
                truly_new_ads_hash = []
                for ad in new_ads:
                    ad_hash = self._hash_ad(ad)
                    if ad_hash not in self.seen_ads:
                        self.seen_ads.add(ad_hash)
                        truly_new_ads_hash.append(ad_hash)
                        truly_new_ads.append(ad)

                if truly_new_ads:
                    self.log_callback(
                        f"✅ Encontrou {len(truly_new_ads)} anúncios ainda não vistos")
                    # Format the message to include title and URL
                    formatted_ads = [
                        f"Título: {ad['title']}\nURL: {ad['url']}" for ad in truly_new_ads]

                    try:
                        # Split messages into batches of 20
                        messages = self._split_message(formatted_ads)
                        for msg in messages:
                            self.telegram_bot.send_message(self.chat_id, msg)
                            time.sleep(1)  # Avoid rate limiting
                        # Only if sending works, add the new ad hashes to file
                        # IMPORTANT this is the persistance mechanism
                        for ad_hash in truly_new_ads_hash:
                            self._save_ad_hash(ad_hash)
                    except Exception as e:
                        self.log_callback(
                            f"❌ Erro ao enviar mensagens para Telegram: {str(e)}")
                    self.log_callback(
                        f"✅ Enviados {len(truly_new_ads)} novos anúncios para Telegram")
                else:
                    self.log_callback("ℹ️ Nenhum anúncio novo encontrado")
            except Exception as e:
                self.log_callback(f"❌ Erro durante verificação: {str(e)}")

            seconds_in_minute = 60
            minutes_to_wait = 30
            seconds_to_wait = minutes_to_wait * seconds_in_minute  # 15 minutes

            # seconds_to_wait = 15  # 15 seconds
            # Wait with countdown
            if self.running:
                self.log_callback(
                    f"⏳ Aguardando próxima verificação ({seconds_to_wait/60} minutos)...")
                for i in range(seconds_to_wait):  # Count down seconds
                    if not self.running:
                        break
                    time.sleep(1)

    def _split_message(self, ads):
        """Split ads into batches and format them into messages"""
        messages = []
        for i in range(0, len(ads), self.batch_size):
            batch = ads[i:i + self.batch_size]
            selected_emoji = emoji_sorter.get_random_emoji()
            message_header = f"{selected_emoji} Novos anúncios encontrados (parte {len(messages) + 1} de {(len(ads) + self.batch_size - 1) // self.batch_size}):\n\n"
            message_content = "\n\n".join(batch)
            messages.append(message_header + message_content)
        return messages

    def stop(self):
        """Stops the monitoring."""
        self.running = False
        self.log_callback("🛑 Comando de parada enviado...")
