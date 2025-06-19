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
import glob

app = Flask(__name__, template_folder='template')

# Configuração de logging
log_file = 'app.log'
file_handler = TimedRotatingFileHandler(
    log_file,
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

# Carrega variáveis de ambiente ANTES de qualquer definição de configuração
load_dotenv()

# --- VARIÁVEIS GLOBAIS FIXAS (LIDAS APENAS UMA VEZ DO .env) ---
# Estas variáveis não serão salvas/lidas do config.json dinamicamente
# Elas são definidas uma vez na inicialização do app.

BASE_URL = os.getenv("MAIN_URL_SCRAPE_ROXO", "")
if not BASE_URL:
    logger.error("Variável de ambiente MAIN_URL_SCRAPE_ROXO não está definida ou está vazia.")
    raise ValueError("Variável de ambiente MAIN_URL_SCRAPE_ROXO não está definida ou está vazia.")

USERNAME = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

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

# --- GERENCIAMENTO DO config.json PARA CONFIGURAÇÕES DINÂMICAS DO MONITOR ---
CONFIG_FILE_PATH = 'config.json'

def load_and_create_monitor_config():
    """Carrega as configurações do monitor do config.json. Cria o arquivo se não existir."""
    if not os.path.exists(CONFIG_FILE_PATH):
        initial_config = {
            "keywords": "",
            "negative_keywords_list": "",
            "token": "",
            "chat_input": ""
        }
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(initial_config, f, indent=2)
            logger.info(f"Arquivo '{CONFIG_FILE_PATH}' criado com configurações iniciais do monitor.")
        except IOError as e:
            logger.error(f"Erro ao criar o arquivo de configuração '{CONFIG_FILE_PATH}': {e}")
            return {}
    
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON do arquivo '{CONFIG_FILE_PATH}': {e}. Retornando configuração vazia.")
        return {}
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar {CONFIG_FILE_PATH}: {e}")
        return {}

def save_monitor_config(new_config_data):
    """Salva as configurações do monitor no config.json."""
    current_config = load_and_create_monitor_config() # Carrega o estado atual
    current_config.update(new_config_data) # Atualiza apenas as chaves do monitor
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, indent=2)
        logger.info(f"Configurações do monitor salvas em '{CONFIG_FILE_PATH}'.")
    except IOError as e:
        logger.error(f"Erro ao salvar configurações do monitor em '{CONFIG_FILE_PATH}': {e}")


# Instância global do Monitor
monitor = None
monitor_thread = None

# Funções de status do monitor (mantidas como antes)
def save_monitor_status(status):
    try:
        with open('monitor_status.json', 'w') as f:
            json.dump({'is_running': status}, f)
    except Exception as e:
        logger.error(f"Erro ao salvar estado do monitor: {str(e)}")

def load_monitor_status():
    try:
        if os.path.exists('monitor_status.json'):
            with open('monitor_status.json', 'r') as f:
                return json.load(f).get('is_running', False)
        return False
    except Exception as e:
        logger.error(f"Erro ao carregar estado do monitor: {str(e)}")
        return False

# Funções de autenticação (mantidas como antes)
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

# --- ROTAS FLASK ---
@app.route('/')
def home():
    """Rota pública que retorna a página principal."""
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
    """Rota protegida que retorna a página de administração."""
    # Sempre lê as configurações mais recentes do monitor no config.json
    monitor_config = load_and_create_monitor_config()
    
    # As variáveis aqui refletem APENAS as configurações do monitor
    # As chaves 'token', 'keywords', etc. SEMPRE virão do config.json
    # (ou serão vazias/padrão se config.json não tiver)
    # Não usamos os.getenv aqui para as configurações do monitor, pois a intenção
    # é que elas sejam gerenciadas pela interface e persistidas no config.json.
    keywords_list_val = monitor_config.get("keywords", "")
    negative_keywords_list_val = monitor_config.get("negative_keywords_list", "")
    token_val = monitor_config.get("token", "")
    chat_input_val = monitor_config.get("chat_input", "")

    return render_template(
        'admin.html',
        keywords_list=keywords_list_val,
        negative_keywords_list=negative_keywords_list_val,
        token=token_val,
        chat_input=chat_input_val,
        username=USERNAME, # Estes ainda vêm de variáveis globais (do .env)
        password=PASSWORD  # Estes ainda vêm de variáveis globais (do .env)
    )

@app.route('/start', methods=['POST'])
@requires_auth
def start():
    global monitor, monitor_thread
    try:
        if load_monitor_status():
            logger.info("Monitoramento já está ativo")
            return {"message": "Monitoramento já está ativo!"}, 400

        data = request.get_json()
        keywords_list_str = data.get('keywords_list', '') # Pega o que foi enviado ou string vazia
        negative_keywords_list_str = data.get('negative_keywords_list', '')
        token = data.get('token', '')
        chat_input = data.get('chat_input', '')

        # Salva AS CONFIGURAÇÕES DO MONITOR recebidas na requisição no config.json
        save_monitor_config({
            "keywords": keywords_list_str,
            "negative_keywords_list": negative_keywords_list_str,
            "token": token,
            "chat_input": chat_input
        })

        keywords_list = [kw.strip() for kw in keywords_list_str.split(",") if kw.strip()]
        negative_keywords_list = [
            kw.strip() for kw in negative_keywords_list_str.split(",") if kw.strip()]
        
        telegram_bot = TelegramBot(log_callback=logger.info, token=token)
        scraper = MarketRoxoScraperCloudflare(
            log_callback=logger.info, 
            base_url=BASE_URL, # BASE_URL é uma variável global (do .env)
            proxies=PROXIES,   # PROXIES é uma variável global (do .env)
        )

        filtered_keywords = [
            kw for kw in keywords_list if kw not in negative_keywords_list]

        monitor = Monitor(
            keywords=filtered_keywords,
            negative_keywords_list=negative_keywords_list,
            scraper=scraper,
            telegram_bot=telegram_bot,
            chat_id=chat_input,
            log_callback=logger.info
        )

        logger.info(f"Monitor criado: {monitor}")
        monitor_thread = Thread(target=monitor.start)
        monitor_thread.daemon = True
        monitor_thread.start()
        logger.info(f"Monitor thread iniciada: {monitor_thread.is_alive()}")
        save_monitor_status(True)

        logger.info(
            f"Monitoramento iniciado com palavras-chave: {', '.join(filtered_keywords)}, chat_id: {chat_input}")
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
        if not load_monitor_status():
            logger.info("Nenhum monitoramento ativo para parar")
            return {"message": "Nenhum monitoramento ativo para parar"}, 400

        if monitor:
            monitor.stop()
            if monitor_thread and monitor_thread.is_alive():
                monitor_thread.join(timeout=10)
            monitor = None
            monitor_thread = None
            save_monitor_status(False)
            logger.info("Monitoramento parado com sucesso")
            return {"message": "Monitoramento parado com sucesso!"}, 200
        else:
            logger.info("Monitoramento não encontrado, mas estado indica que estava ativo")
            save_monitor_status(False)
            return {"message": "Monitoramento parado com sucesso!"}, 200
    except Exception as e:
        logger.error(f"Erro ao parar monitoramento: {str(e)}")
        return {"message": f"Erro ao parar monitoramento: {str(e)}"}, 500

@app.route('/logs')
@requires_auth
def logs():
    """Retorna o conteúdo dos arquivos de log disponíveis ou de um arquivo específico."""
    log_dir = os.path.dirname(log_file)
    if not log_dir:
        log_dir = '.' 

    log_files_pattern = os.path.join(log_dir, os.path.basename(log_file) + '*')
    all_log_files = glob.glob(log_files_pattern)
    
    log_files_with_mtime = []
    for f in all_log_files:
        try:
            mtime = os.path.getmtime(f)
            log_files_with_mtime.append((mtime, os.path.basename(f)))
        except FileNotFoundError:
            continue

    sorted_display_log_files = [f_name for mtime, f_name in sorted(log_files_with_mtime, key=lambda x: x[0], reverse=True)]

    requested_log = request.args.get('file')

    try:
        if requested_log:
            if requested_log in sorted_display_log_files:
                file_path = os.path.join(log_dir, requested_log)
                with open(file_path, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                return Response(log_content, mimetype='text/plain')
            else:
                return {"message": f"Arquivo de log '{requested_log}' não encontrado ou inválido."}, 404
        else:
            log_list_html = "<h1>Logs Disponíveis</h1><ul>"
            if os.path.basename(log_file) in sorted_display_log_files:
                log_list_html += f'<li><a href="/logs?file={os.path.basename(log_file)}">{os.path.basename(log_file)} (Atual)</a></li>'
            
            for log_file_name in sorted_display_log_files:
                if log_file_name != os.path.basename(log_file):
                    log_list_html += f'<li><a href="/logs?file={log_file_name}">{log_file_name}</a></li>'
            log_list_html += "</ul>"
            return Response(log_list_html, mimetype='text/html')

    except Exception as e:
        logger.error(f"Erro ao ler logs: {str(e)}")
        return {"message": f"Erro ao ler logs: {str(e)}"}, 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=False, processes=1)