from flask import Flask, Response, request, render_template, send_file, jsonify
from functools import wraps
import os
import fcntl
from dotenv import load_dotenv
import json
from monitor import Monitor
from scraper_cloudflare import MarketRoxoScraperCloudflare
from telegram_bot import TelegramBot
import zipfile
import io
from datetime import datetime, timezone, timedelta
from logging_config import get_logger, setup_logging, GMT3Formatter
from concurrent_log_handler import ConcurrentRotatingFileHandler

app = Flask(__name__, template_folder='template')

# Configura o logger no início da aplicação
setup_logging()

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações ---
CONFIG_FILE_PATH = 'config.json'
LOGS_DIR = 'logs'
LOCK_FILE = 'monitor.lock'

def load_dynamic_config():
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        get_logger().error(f"Erro ao carregar config.json: {e}")
        return {}

def save_dynamic_config(data):
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        get_logger().info("Configurações salvas em config.json")
    except Exception as e:
        get_logger().error(f"Erro ao salvar config.json: {e}")

# Configurações globais
initial_config = load_dynamic_config()
TELEGRAM_TOKEN = initial_config.get("token", os.getenv("TELEGRAM_TOKEN", ""))
CHAT_INPUT = initial_config.get("chat_input", os.getenv("TELEGRAM_CHAT_ID_OR_PHONE", ""))
DEFAULT_KEYWORDS = initial_config.get("keywords", os.getenv("DEFAULT_KEYWORDS", "iphone, samsung, xiaomi"))
NEGATIVE_KEYWORDS = initial_config.get("negative_keywords_list", os.getenv("NEGATIVE_KEYWORDS_LIST", ""))

BASE_URL = os.getenv("MAIN_URL_SCRAPE_ROXO", "")
if not BASE_URL:
    raise ValueError("MAIN_URL_SCRAPE_ROXO não definida")

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

# Variável do monitor
monitor = None

def acquire_lock():
    """Tenta adquirir o lock file para garantir uma única instância do monitor"""
    try:
        lock_file = open(LOCK_FILE, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        lock_file.close()
        return None

def release_lock(lock_file):
    """Libera o lock file"""
    if lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

def is_monitor_running():
    """Verifica se o monitor está rodando tentando adquirir o lock"""
    lock_file = acquire_lock()
    if lock_file:
        release_lock(lock_file)
        return False
    return True

# --- Autenticação ---
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

# Função para ser chamada após o fork de cada worker no servidor
def post_fork(server, worker):
    """Configura o logging em cada worker após o fork"""
    setup_logging()
    get_logger().info(f"Worker {worker.pid} inicializado com logging configurado")

# --- Rotas ---
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
    current_config = load_dynamic_config()
    
    return render_template(
        'admin.html',
        keywords_list=current_config.get("keywords", DEFAULT_KEYWORDS),
        negative_keywords_list=current_config.get("negative_keywords_list", NEGATIVE_KEYWORDS),
        token=current_config.get("token", TELEGRAM_TOKEN),
        chat_input=current_config.get("chat_input", CHAT_INPUT),
        interval_monitor=current_config.get("interval_monitor", 30),
        page_depth=current_config.get("page_depth", 3),
        retry_attempts=current_config.get("retry_attempts", 100),
        min_repeat_time=current_config.get("min_repeat_time", 15),
        max_repeat_time=current_config.get("max_repeat_time", 67),
        allow_keyword_subsets=current_config.get("allow_subset", False),
        batch_size=current_config.get("batch_size", 1),
        number_set=current_config.get("number_set", 4),
        username=USERNAME,
        password=PASSWORD
    )

@app.route('/start', methods=['POST'])
@requires_auth
def start():
    global monitor
    
    lock_file = acquire_lock()
    if not lock_file:
        get_logger().info("Tentativa de iniciar monitoramento enquanto já está ativo")
        return {"message": "Monitoramento já está ativo!"}, 400
    
    try:
        data = request.get_json()
        
        config = {
            "keywords": data.get('keywords_list', DEFAULT_KEYWORDS),
            "negative_keywords_list": data.get('negative_keywords_list', NEGATIVE_KEYWORDS),
            "token": data.get('token', TELEGRAM_TOKEN),
            "chat_input": data.get('chat_input', CHAT_INPUT),
            "interval_monitor": int(data.get('interval_monitor', 30)),
            "page_depth": int(data.get('page_depth', 3)),
            "retry_attempts": int(data.get('retry_attempts', 100)),
            "min_repeat_time": int(data.get('min_repeat_time', 15)),
            "max_repeat_time": int(data.get('max_repeat_time', 67)),
            "allow_subset": data.get('allow_subset', False),
            "batch_size": int(data.get('batch_size', 1)),
            "number_set": int(data.get('number_set', 4))
        }
        
        save_dynamic_config(config)
        
        keywords_list = [kw.strip() for kw in config["keywords"].split(",") if kw.strip()]
        negative_keywords_list = [kw.strip() for kw in config["negative_keywords_list"].split(",") if kw.strip()]
        
        telegram_bot = TelegramBot(token=config["token"])
        scraper = MarketRoxoScraperCloudflare(
            base_url=BASE_URL,
            proxies=PROXIES
        )
        
        monitor = Monitor(
            keywords=keywords_list,
            negative_keywords_list=negative_keywords_list,
            scraper=scraper,
            telegram_bot=telegram_bot,
            chat_id=config["chat_input"],
            batch_size=config["batch_size"],
            number_set=config["number_set"],
            monitoring_interval=config["interval_monitor"],
            page_depth=config["page_depth"],
            retry_attempts=config["retry_attempts"],
            min_repeat_time=config["min_repeat_time"],
            max_repeat_time=config["max_repeat_time"],
            allow_subset=config["allow_subset"],
            min_subset_size=max(2, len(keywords_list) // 2),
            max_subset_size=len(keywords_list)
        )
        
        if not monitor.start_async():
            release_lock(lock_file)
            monitor = None
            return {"message": "Erro ao iniciar monitoramento: já está ativo"}, 500
        
        get_logger().info(f"Monitoramento iniciado com {len(keywords_list)} palavras-chave")
        return {"message": "Monitoramento iniciado com sucesso!"}, 200
        
    except Exception as e:
        get_logger().error(f"Erro ao iniciar monitoramento: {str(e)}")
        release_lock(lock_file)
        monitor = None
        return {"message": f"Erro ao iniciar: {str(e)}"}, 500
    finally:
        # Keep the lock file open until the monitor stops
        pass

@app.route('/stop', methods=['POST'])
@requires_auth
def stop():
    global monitor
    
    if not is_monitor_running():
        get_logger().info("Nenhum monitoramento ativo detectado")
        return {"message": "Nenhum monitoramento ativo"}, 400
    
    try:
        if monitor and monitor.is_running:
            success = monitor.stop()
            if success:
                get_logger().info("Monitoramento encerrado com sucesso")
                monitor = None
                release_lock_file()
                return {"message": "Monitoramento encerrado com sucesso!"}, 200
            else:
                get_logger().warning("Falha ao encerrar monitoramento, mantendo monitor para nova tentativa")
                return {"message": "Falha ao encerrar monitoramento, tente novamente"}, 500
        else:
            get_logger().info("Nenhum monitor local ativo, mas lock file existe")
            return {"message": "Monitoramento ativo em outro processo, tente novamente"}, 400
    except Exception as e:
        get_logger().error(f"Erro ao encerrar monitoramento: {str(e)}")
        return {"message": f"Erro ao encerrar: {str(e)}"}, 500

def release_lock_file():
    """Libera o lock file se existir"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            os.remove(LOCK_FILE)
            get_logger().info("Lock file removido com sucesso")
        except Exception as e:
            get_logger().error(f"Erro ao remover lock file: {str(e)}")

@app.route('/logs')
@requires_auth
def logs():
    try:
        log_file_path = os.path.join(LOGS_DIR, 'app.log')
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        get_logger().debug("Logs acessados via /logs")
        return Response(content, mimetype='text/plain')
    except FileNotFoundError:
        get_logger().error("Arquivo de log não encontrado")
        return {"message": "Arquivo de log não encontrado"}, 404
    except Exception as e:
        get_logger().error(f"Erro ao ler logs: {str(e)}")
        return {"message": f"Erro ao ler logs: {str(e)}"}, 500

@app.route('/archive_log', methods=['GET'])
@requires_auth
def archive_log():
    try:
        logger = get_logger()
        gmt_minus_3 = timezone(timedelta(hours=-3))
        timestamp = datetime.now(gmt_minus_3).strftime("%Y-%m-%d_%H-%M-%S")
        log_file_path = os.path.join(LOGS_DIR, 'app.log')
        
        for handler in logger.handlers:
            if isinstance(handler, ConcurrentRotatingFileHandler):
                handler.close()
                if os.path.exists(log_file_path):
                    archived_name = f"{log_file_path}.{timestamp}"
                    os.rename(log_file_path, archived_name)
                open(log_file_path, 'a').close()  # Cria novo arquivo vazio
                new_handler = ConcurrentRotatingFileHandler(
                    log_file_path,
                    maxBytes=10**10,
                    backupCount=7,
                    encoding='utf-8'
                )
                formatter = GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s')
                new_handler.setFormatter(formatter)
                logger.removeHandler(handler)
                logger.addHandler(new_handler)
                logger.info(f"Log rotacionado para {archived_name}")
        return jsonify({"message": "Log arquivado com sucesso"}), 200
    except Exception as e:
        get_logger().error(f"Erro ao arquivar log: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download-logs', methods=['GET'])
@requires_auth
def download_logs():
    try:
        log_files = []
        if os.path.exists(LOGS_DIR):
            log_files = [os.path.join(LOGS_DIR, f) for f in os.listdir(LOGS_DIR) if f.endswith('.log')]
        
        if not log_files:
            get_logger().error("Nenhum arquivo de log encontrado")
            return jsonify({'message': 'Nenhum arquivo de log encontrado'}), 404
        
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, 'w') as zf:
            for log_file in log_files:
                zf.write(log_file, arcname=os.path.basename(log_file))
        
        mem_zip.seek(0)
        get_logger().info("Logs baixados via /download-logs")
        return send_file(mem_zip, mimetype='application/zip', 
                        as_attachment=True, download_name='all_logs.zip')
    except Exception as e:
        get_logger().error(f"Erro ao baixar logs: {str(e)}")
        return {"message": f"Erro ao baixar logs: {str(e)}"}, 500

@app.route('/download-hash-file', methods=['GET'])
@requires_auth
def download_hash_file():
    data_dir = os.path.join(os.path.expanduser("~"), ".marketroxo_data")
    hash_file_path = os.path.join(data_dir, "seen_ads.txt")
    
    if not os.path.exists(hash_file_path):
        get_logger().error("Arquivo hash não encontrado")
        return {"message": "Arquivo hash não encontrado"}, 404
    
    get_logger().info("Arquivo hash baixado via /download-hash-file")
    return send_file(hash_file_path, as_attachment=True)

if __name__ == '__main__':
    get_logger().info("Aplicação iniciada - Market Roxo Monitor")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=False, processes=1)