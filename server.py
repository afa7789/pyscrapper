from flask import Flask, Response, request, render_template
from functools import wraps
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from dotenv import load_dotenv
import json
from threading import Thread
from monitor import Monitor
from scraper_cloudflare import MarketRoxoScraperCloudflare
from telegram_bot import TelegramBot
from flask import send_file
from datetime import datetime
from flask import jsonify, send_from_directory, abort
import zipfile
import io

app = Flask(__name__, template_folder='template')

# --- Configuração de Logging com Rotação Diária ---
LOGS_DIR = 'logs'  # Dedicated directory for all logs
os.makedirs(LOGS_DIR, exist_ok=True) # Ensure the directory exists

log_file_base = 'app' # Base name for the current log file
log_file_path = os.path.join(LOGS_DIR, f'{log_file_base}.log')

file_handler = TimedRotatingFileHandler(
    log_file_path, # Path includes the logs directory
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname).1s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

# Carrega variáveis de ambiente
load_dotenv()

# --- GERENCIAMENTO DO config.json ---
CONFIG_FILE_PATH = 'config.json'


def load_dynamic_config():
    """
    Tenta carregar as configurações dinâmicas do config.json.
    Retorna dicionário vazio se o arquivo não existir ou for inválido.
    """
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}  # Retorna vazio se o arquivo não existe
    except json.JSONDecodeError as e:
        logger.error(
            f"Erro ao decodificar JSON do arquivo '{CONFIG_FILE_PATH}': {e}. Retornando configuração vazia.")
        return {}  # Retorna vazio se o JSON for inválido
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar {CONFIG_FILE_PATH}: {e}")
        return {}

def save_dynamic_config(data_to_save):
    """
    Salva as configurações dinâmicas no config.json.
    Sobrescreve o conteúdo existente com os novos dados.
    """
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2)
        logger.info(f"Configurações dinâmicas salvas em '{CONFIG_FILE_PATH}'.")
    except IOError as e:
        logger.error(
            f"Erro ao salvar configurações dinâmicas em '{CONFIG_FILE_PATH}': {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar config.json: {e}")

# --- Variáveis Globais (Lidas na Inicialização) ---
# Estas variáveis têm a seguinte prioridade:
# 1. config.json (se existir e tiver a chave)
# 2. .env (via os.getenv)
# 3. Valor padrão hardcoded no código


# Carrega configurações dinâmicas uma vez na inicialização para variáveis globais
initial_dynamic_config = load_dynamic_config()

TELEGRAM_TOKEN = initial_dynamic_config.get(
    "token", os.getenv("TELEGRAM_TOKEN", ""))
CHAT_INPUT = initial_dynamic_config.get(
    "chat_input", os.getenv("TELEGRAM_CHAT_ID_OR_PHONE", ""))
DEFAULT_KEYWORDS = initial_dynamic_config.get(
    "keywords", os.getenv("DEFAULT_KEYWORDS", "iphone, samsung, xiaomi"))
NEGATIVE_KEYWORDS = initial_dynamic_config.get(
    "negative_keywords_list", os.getenv("NEGATIVE_KEYWORDS_LIST", ""))

BASE_URL = os.getenv("MAIN_URL_SCRAPE_ROXO", "")
if not BASE_URL:
    logger.error(
        "Variável de ambiente MAIN_URL_SCRAPE_ROXO não está definida ou está vazia.")
    raise ValueError(
        "Variável de ambiente MAIN_URL_SCRAPE_ROXO não está definida ou está vazia.")

# Credenciais para Basic Auth (sempre do .env ou padrão)
USERNAME = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

# Variáveis da Empresa (sempre do .env ou padrão)
COMPANY_TITLE = os.getenv("COMPANY_TITLE", "")
COMPANY_SLOGAN = os.getenv("COMPANY_SLOGAN", "")
COMPANY_DESCRIPTION = os.getenv("COMPANY_DESCRIPTION", "")
COMPANY_LOCATION = os.getenv("COMPANY_LOCATION", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
PHONE_DISPLAY = os.getenv("PHONE_DISPLAY", "")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "")
WHATSAPP_TEXT = os.getenv("WHATSAPP_TEXT", "")
WEBSITE = os.getenv("WEBSITE", "")

PROXIES = {
    "http": os.getenv("HTTP_PROXY", ""),
    "https": os.getenv("HTTPS_PROXY", "")
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Instância global do Monitor
monitor = None
monitor_thread = None


def save_monitor_status(status):
    """Salva o status de execução do monitor em um arquivo."""
    try:
        with open('monitor_status.json', 'w', encoding='utf-8') as f:
            json.dump({'is_running': status}, f)
    except Exception as e:
        logger.error(f"Erro ao salvar estado do monitor: {str(e)}")


def load_monitor_status():
    """Carrega o status de execução do monitor de um arquivo."""
    try:
        if os.path.exists('monitor_status.json'):
            with open('monitor_status.json', 'r', encoding='utf-8') as f:
                return json.load(f).get('is_running', False)
        return False
    except Exception as e:
        logger.error(f"Erro ao carregar estado do monitor: {str(e)}")
        return False

# --- Lógica de Auth (sem mudanças) ---

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD


def authenticate():
    return Response(
        'Autenticação necessária.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- Rotas Flask ---
@app.route('/download-hash-file', methods=['GET'])
@requires_auth
def download_hash_file():
    data_dir = os.path.join(os.path.expanduser("~"), ".marketroxo_data")
    os.makedirs(data_dir, exist_ok=True)
    hash_file_path = os.path.join(data_dir, "seen_ads.txt")

    if not os.path.exists(hash_file_path):
        logger.info(f"Hash file not found at: {hash_file_path}")
        return {"message": "Hash file not found."}, 404

    return send_file(hash_file_path, as_attachment=True)


@app.route('/')
def home():
    return render_template(
        'index.html',
        company_title=COMPANY_TITLE,
        company_slogan=COMPANY_SLOGAN,
        company_description=COMPANY_DESCRIPTION,
        company_location=COMPANY_LOCATION,
        phone_number=PHONE_NUMBER,
        phone_display=PHONE_DISPLAY,
        whatsapp_number=WHATSAPP_NUMBER,
        whatsapp_text=WHATSAPP_TEXT,
        website=WEBSITE
    )


@app.route('/admin')
@requires_auth
def admin():
    # Sempre recarrega as configurações dinâmicas do config.json para ter os valores mais recentes
    current_dynamic_config = load_dynamic_config()

    # As variáveis para o template seguem a prioridade: config.json > .env > padrão
    keywords_list_val = current_dynamic_config.get(
        "keywords", os.getenv("DEFAULT_KEYWORDS", "iphone, samsung, xiaomi"))
    negative_keywords_list_val = current_dynamic_config.get(
        "negative_keywords_list", os.getenv("NEGATIVE_KEYWORDS_LIST", ""))
    token_val = current_dynamic_config.get(
        "token", os.getenv("TELEGRAM_TOKEN", ""))
    chat_input_val = current_dynamic_config.get(
        "chat_input", os.getenv("TELEGRAM_CHAT_ID_OR_PHONE", ""))
    page_depth_val = current_dynamic_config.get("page_depth", 3)
    retry_attempts_val = current_dynamic_config.get("retry_attempts", 100)
    min_repeat_time_val = current_dynamic_config.get("min_repeat_time", 15)
    interval_monitor_val = current_dynamic_config.get("interval_monitor", 30) 
    max_repeat_time_val = current_dynamic_config.get("max_repeat_time", 67)
    allow_subset_val = current_dynamic_config.get("allow_subset", False)
    batch_size_val = current_dynamic_config.get("batch_size", 1)

    return render_template(
        'admin.html',
        keywords_list=keywords_list_val,
        negative_keywords_list=negative_keywords_list_val,
        token=token_val,
        chat_input=chat_input_val,
        interval_monitor=interval_monitor_val,
        page_depth=page_depth_val,
        retry_attempts=retry_attempts_val,
        min_repeat_time=min_repeat_time_val,
        max_repeat_time=max_repeat_time_val,
        allow_keyword_subsets=allow_subset_val,
        batch_size=batch_size_val,
        username=USERNAME,
        password=PASSWORD
    )


@app.route('/start', methods=['POST'])
@requires_auth
def start():
    global monitor, monitor_thread
    try:
        # Verifica se um monitor JÁ ESTÁ ATIVO NESTE PROCESSO
        # E também verifica o status persistido para evitar iniciar duas vezes
        if monitor and monitor_thread and monitor_thread.is_alive():
            logger.info(
                "Monitoramento já está ativo (verificado por variável global)")
            return {"message": "Monitoramento já está ativo!"}, 400

        if load_monitor_status():  # Verifica o status persistido
            logger.info(
                "Monitoramento já está ativo (verificado por monitor_status.json)")
            # Tenta parar o monitor persistido se ele não estiver rodando neste processo.
            # Isso pode acontecer se o app foi reiniciado e o status_json ficou 'true'.
            # Mas idealmente, para um server.py único, 'monitor' e 'monitor_thread' devem ser None
            # se não houver um monitor ativo neste processo.
            # Se load_monitor_status() é true mas monitor é None, é um estado "sujo".
            # Vamos forçar a parada para limpar.
            logger.warning(
                "monitor_status.json indica ativo, mas variáveis globais são None. Forçando reset.")
            # Reseta o status para permitir um novo início.
            save_monitor_status(False)
            # A requisição continuará para iniciar o monitor agora.

        data = request.get_json()

        keywords_list_str = data.get('keywords_list', DEFAULT_KEYWORDS)
        negative_keywords_list_str = data.get(
            'negative_keywords_list', NEGATIVE_KEYWORDS)
        token = data.get('token', TELEGRAM_TOKEN)
        chat_input = data.get('chat_input', CHAT_INPUT)
        page_depth = int(data.get('page_depth', 3))
        retry_attempts = int(data.get('retry_attempts', 100))
        min_repeat_time = int(data.get('min_repeat_time', 15))
        max_repeat_time = int(data.get('max_repeat_time', 67))
        allow_subset = data.get('allow_subset', False)
        interval_monitor = int(data.get('interval_monitor', 30))
        batch_size = int(data.get('batch_size', 1))

        data_to_save = {
            "keywords": keywords_list_str,
            "negative_keywords_list": negative_keywords_list_str,
            "token": token,
            "chat_input": chat_input,
            "interval_monitor": interval_monitor, 
            "batch_size": batch_size, 
            "page_depth": page_depth,
            "retry_attempts": retry_attempts,
            "min_repeat_time": min_repeat_time,
            "max_repeat_time": max_repeat_time,
            "allow_subset": allow_subset
        }
        save_dynamic_config(data_to_save)

        keywords_list = [kw.strip()
                         for kw in keywords_list_str.split(",") if kw.strip()]
        negative_keywords_list = [
            kw.strip() for kw in negative_keywords_list_str.split(",") if kw.strip()]

        telegram_bot = TelegramBot(log_callback=logger.info, token=token)
        scraper = MarketRoxoScraperCloudflare(
            log_callback=logger.info,
            base_url=BASE_URL,
            proxies=PROXIES,
        )

        filtered_keywords = [
            kw for kw in keywords_list if kw not in negative_keywords_list]

        min_subset_size = max(2, len(filtered_keywords) // 2)
        max_subset_size = len(filtered_keywords)

        monitor = Monitor(
            keywords=filtered_keywords,
            negative_keywords_list=negative_keywords_list,
            scraper=scraper,
            telegram_bot=telegram_bot,
            chat_id=chat_input,
            batch_size=batch_size,
            monitoring_interval=interval_monitor,
            log_callback=logger.info,
            page_depth=page_depth,
            retry_attempts=retry_attempts,
            min_repeat_time=min_repeat_time,
            max_repeat_time=max_repeat_time,
            allow_subset=allow_subset,
            min_subset_size=min_subset_size,
            max_subset_size=max_subset_size
        )

        logger.info(f"Monitor criado: {monitor}")
        monitor_thread = Thread(target=monitor.start)
        monitor_thread.daemon = True
        monitor_thread.start()
        logger.info(f"Monitor thread iniciada: {monitor_thread.is_alive()}")
        save_monitor_status(True)

        logger.info(
            f"Monitoramento iniciado com palavras-chave: {', '.join(filtered_keywords)}, chat_id: {chat_input}, page_depth: {page_depth}, retry_attempts: {retry_attempts}, min_repeat_time: {min_repeat_time}, max_repeat_time: {max_repeat_time}")
        return {"message": "Monitoramento iniciado com sucesso!"}, 200
    except Exception as e:
        logger.error(f"Erro ao iniciar monitoramento: {str(e)}")
        return {"message": f"Erro ao iniciar monitoramento: {str(e)}"}, 500


@app.route('/stop', methods=['POST'])
@requires_auth
def stop():
    global monitor, monitor_thread
    logger.info(f"Estado do monitor antes de parar: {monitor}")
    logger.info(f"Estado da thread antes de parar: {monitor_thread}")
    try:
        # Verifica se o monitor está ativo NESTE PROCESSO
        if monitor and monitor_thread and monitor_thread.is_alive():
            monitor.stop()
            monitor_thread.join(timeout=10)  # Aguarda a thread terminar
            monitor = None
            monitor_thread = None
            save_monitor_status(False)  # Limpa o status persistido
            logger.info("Monitoramento parado com sucesso")
            return {"message": "Monitoramento parado com sucesso!"}, 200
        elif load_monitor_status():  # Se não está ativo aqui, mas o arquivo diz que está
            logger.warning(
                "Monitoramento não ativo neste processo, mas monitor_status.json indica ativo. Resetando.")
            save_monitor_status(False)  # Apenas limpa o arquivo
            return {"message": "Monitoramento já estava parado (status resetado)."}, 200
        else:
            logger.info("Nenhum monitoramento ativo para parar")
            return {"message": "Nenhum monitoramento ativo para parar"}, 400
    except Exception as e:
        logger.error(f"Erro ao parar monitoramento: {str(e)}")
        return {"message": f"Erro ao parar monitoramento: {str(e)}"}, 500


@app.route('/logs')
@requires_auth
def logs():
    """Retorna o conteúdo do arquivo de log ATUAL (app.log)."""
    try:
        # Use log_file_path which points to the current log file in the LOGS_DIR
        with open(log_file_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
        return Response(log_content, mimetype='text/plain')
    except FileNotFoundError:
        return {"message": f"O arquivo de log '{log_file_path}' não foi encontrado."}, 404
    except Exception as e:
        logger.error(f"Erro ao ler logs: {str(e)}")
        return {"message": f"Erro ao ler logs: {str(e)}"}, 500


@app.route('/archive_log', methods=['GET'])
@requires_auth
def archive_log():
    """Arquiva o log atual, renomeando com data/hora, e permite que o RotatingFileHandler crie um novo."""
    try:
        # Call doRollover() to force the TimedRotatingFileHandler to rotate the log.
        # This will rename the current log_file_path (e.g., app.log) to app.log.YYYY-MM-DD
        # and create a new empty app.log for further logging.
        file_handler.doRollover()
        logger.info("Log rotated successfully by doRollover().")
        return jsonify({'message': 'Log atual arquivado. Nova sessão de log iniciada.'})
    except Exception as e:
        logger.error(f"Erro ao arquivar log: {str(e)}")
        return jsonify({'message': f'Erro ao arquivar log: {str(e)}'}), 500


@app.route('/download-logs', methods=['GET'])
@requires_auth
def download_logs():
    """Compacta e baixa todos os logs na pasta 'logs'."""
    try:
        files = []
        if os.path.exists(LOGS_DIR):
            for f in os.listdir(LOGS_DIR):
                if f.endswith('.log'):
                    files.append(os.path.join(LOGS_DIR, f))
        
        if not files:
            return jsonify({'message': 'Nenhum arquivo de log encontrado para download.'}), 404
        
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, 'w') as zf:
            for f in files:
                zf.write(f, arcname=os.path.basename(f)) # Store only filename in zip
        mem_zip.seek(0)
        return send_file(mem_zip, mimetype='application/zip', as_attachment=True, download_name='all_logs.zip')
    except Exception as e:
        logger.error(f"Erro ao compactar logs para download: {str(e)}")
        return jsonify({'message': f'Erro ao baixar logs: {str(e)}'}), 500


# Este bloco só é executado quando o script é o principal
if __name__ == '__main__':
    # Ao iniciar o aplicativo, garanta que o status persistido do monitor seja FALSO.
    # Isso evita problemas se o aplicativo foi encerrado de forma inesperada.
    # Apenas se o monitor *realmente* está rodando, o status será True.
    save_monitor_status(False)
    app.run(debug=False, host='0.0.0.0',
            port=5000, threaded=False, processes=1)