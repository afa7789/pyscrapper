from flask import Flask, Response, request, render_template, send_file, jsonify
from functools import wraps
import os
import fcntl
import psutil
from dotenv import load_dotenv
import json
from monitor import Monitor
from scraper_cloudflare import MarketRoxoScraperCloudflare
from telegram_bot import TelegramBot
import zipfile
import io
from datetime import datetime, timezone, timedelta
from logging_config import setup_4hour_rotation, get_logger, force_log_rotation
# setup_logging, setup_frequent_rotation, setup_hourly_rotation
from concurrent_log_handler import ConcurrentRotatingFileHandler

app = Flask(__name__, template_folder='template')


# Substitua a linha onde você configura o logging:
# Antes: setup_logging()
# Agora escolha uma das opções:

# OPÇÃO 1: Rotação a cada 4 horas (recomendado)
setup_4hour_rotation()

# OPÇÃO 2: Rotação a cada 10MB (para logs muito verbosos)
# setup_frequent_rotation()

# OPÇÃO 3: Rotação a cada 1 hora (para monitoramento intensivo)
# setup_hourly_rotation()

# OPÇÃO 4: Configuração personalizada
# setup_logging(rotation_type='time', rotation_interval=6)  # A cada 6 horas
# setup_logging(rotation_type='size', rotation_interval=5)  # A cada 5MB

# Adicione estas novas rotas ao seu server.py:

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
POSITIVE_KEYWORDS = initial_config.get("positive_keywords_list", os.getenv("POSITIVE_KEYWORDS_LIST", ""))

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
lock_file_handle = None

def acquire_lock():
    """Tenta adquirir o lock file e armazena o PID do processo atual"""
    global lock_file_handle
    try:
        lock_file_handle = open(LOCK_FILE, 'w')
        fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        pid = os.getpid()
        lock_file_handle.write(str(pid))
        lock_file_handle.flush()
        get_logger().info(f"Lock adquirido pelo processo {pid}")
        return True
    except IOError:
        if lock_file_handle:
            lock_file_handle.close()
            lock_file_handle = None
        return False

def release_lock():
    """Libera o lock file"""
    global lock_file_handle
    if lock_file_handle:
        try:
            fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_UN)
            lock_file_handle.close()
            lock_file_handle = None
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
            get_logger().info("Lock file removido")
        except OSError as e:
            get_logger().error(f"Erro ao liberar lock: {str(e)}")

def is_monitor_running():
    """Verifica se o monitor está rodando com base no PID no lock file"""
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, 'r') as f:
            pid_str = f.read().strip()
            if pid_str and pid_str.isdigit():
                pid = int(pid_str)
                if psutil.pid_exists(pid):
                    # Verifica se é realmente um processo Python
                    try:
                        process = psutil.Process(pid)
                        cmdline = ' '.join(process.cmdline())
                        if 'python' in cmdline.lower() and ('server' in cmdline or 'gunicorn' in cmdline):
                            return True
                    except psutil.NoSuchProcess:
                        pass
                
                # Se chegou aqui, o PID não existe ou não é um processo válido
                get_logger().info(f"Processo {pid} não existe mais, limpando lock file")
                try:
                    os.remove(LOCK_FILE)
                except OSError:
                    pass
                return False
    except (ValueError, OSError, IOError) as e:
        get_logger().error(f"Erro ao verificar lock file: {e}")
        return False
    return False

def get_monitor_instance():
    """Retorna a instância do monitor se estiver disponível"""
    global monitor
    return monitor

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
    setup_4hour_rotation()
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
    
    # Parse keywords first to get the correct length
    keywords_str = current_config.get('keywords', DEFAULT_KEYWORDS)
    keywords_list = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]

    return render_template(
        'admin.html',
        keywords_list=keywords_str,
        negative_keywords_list=current_config.get("negative_keywords_list", NEGATIVE_KEYWORDS),
        positive_keywords_list=current_config.get("positive_keywords_list", POSITIVE_KEYWORDS),
        token=current_config.get("token", TELEGRAM_TOKEN),
        chat_input=current_config.get("chat_input", CHAT_INPUT),
        interval_monitor=current_config.get("interval_monitor", 30),
        page_depth=current_config.get("page_depth", 3),
        retry_attempts=current_config.get("retry_attempts", 100),
        min_repeat_time=current_config.get("min_repeat_time", 15),
        max_repeat_time=current_config.get("max_repeat_time", 67),
        allow_keyword_subsets=current_config.get("allow_subset", False),
        send_as_batch=current_config.get("send_as_batch", True),
        batch_size=current_config.get("batch_size", 1),
        number_set=current_config.get("number_set", 4),
        min_subset_size=current_config.get("min_subset_size", 3),
        max_subset_size=current_config.get("max_subset_size", len(keywords_list)),
        username=USERNAME,
        password=PASSWORD
    )

@app.route('/health-dashboard')
@requires_auth
def health_dashboard():
    """Página de dashboard de saúde"""
    return render_template('health.html', username=USERNAME, password=PASSWORD)

@app.route('/start', methods=['POST'])
@requires_auth
def start():
    global monitor
    
    if is_monitor_running():
        get_logger().info("Tentativa de iniciar monitoramento enquanto já está ativo")
        return jsonify({"message": "Monitoramento já está ativo!"}), 400
    
    if not acquire_lock():
        get_logger().error("Não foi possível adquirir o lock file")
        return jsonify({"message": "Não foi possível iniciar monitoramento - lock ocupado"}), 500
    
    try:
        data = request.get_json()
        
        # Parse keywords first to get the correct length
        keywords_str = data.get('keywords_list', DEFAULT_KEYWORDS)
        keywords_list = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        
        config = {
            "keywords": keywords_str,
            "negative_keywords_list": data.get('negative_keywords_list', NEGATIVE_KEYWORDS),
            "positive_keywords_list": data.get('positive_keywords_list', POSITIVE_KEYWORDS),
            "token": data.get('token', TELEGRAM_TOKEN),
            "chat_input": data.get('chat_input', CHAT_INPUT),
            "interval_monitor": int(data.get('interval_monitor', 30)),
            "page_depth": int(data.get('page_depth', 3)),
            "retry_attempts": int(data.get('retry_attempts', 100)),
            "min_repeat_time": int(data.get('min_repeat_time', 15)),
            "max_repeat_time": int(data.get('max_repeat_time', 67)),
            "allow_subset": data.get('allow_subset', False),
            "send_as_batch": data.get('send_as_batch', True),
            "batch_size": int(data.get('batch_size', 1)),
            "min_subset_size": int(data.get('min_subset_size', 3)),
            "max_subset_size": int(data.get('max_subset_size', len(keywords_list))),
            "number_set": int(data.get('number_set', 4))
        }
        
        save_dynamic_config(config)
        negative_keywords_list = [kw.strip() for kw in config["negative_keywords_list"].split(",") if kw.strip()]
        positive_keywords_list = [kw.strip() for kw in config["positive_keywords_list"].split(",") if kw.strip()]

        telegram_bot = TelegramBot(token=config["token"])
        scraper = MarketRoxoScraperCloudflare(
            base_url=BASE_URL,
            proxies=PROXIES
        )
        
        monitor = Monitor(
            keywords=keywords_list,
            negative_keywords_list=negative_keywords_list,
            positive_keywords_list=positive_keywords_list,
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
            send_as_batch=config["send_as_batch"],
            min_subset_size=config["min_subset_size"] if len(keywords_list) >= 3 else len(keywords_list),
            max_subset_size=config["max_subset_size"] if config["max_subset_size"] <= len(keywords_list) else len(keywords_list)
        )
        
        if not monitor.start_async():
            release_lock()
            monitor = None
            return jsonify({"message": "Erro ao iniciar monitoramento: já está ativo"}), 500
        
        get_logger().info(f"Monitoramento iniciado com {len(keywords_list)} palavras-chave")
        return jsonify({"message": "Monitoramento iniciado com sucesso!"}, 200)
        
    except Exception as e:
        get_logger().error(f"Erro ao iniciar monitoramento: {str(e)}")
        release_lock()
        monitor = None
        return jsonify({"message": f"Erro ao iniciar: {str(e)}"}), 500

@app.route('/stop', methods=['POST'])
@requires_auth
def stop():
    global monitor
    logger = get_logger()
    
    success = True
    
    # Force stop local monitor thread first
    if monitor:
        try:
            monitor.stop_event.set()
            monitor.is_running = False
            if monitor.thread and monitor.thread.is_alive():
                monitor.thread.join(timeout=5)
                if monitor.thread.is_alive():
                    logger.error("Monitor thread failed to stop within timeout")
                    success = False
                else:
                    logger.info("Local monitor thread stopped")
            monitor = None
        except Exception as e:
            logger.error(f"Error stopping monitor thread: {e}")
            success = False
    
    # Handle PID lock cleanup
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid_str = f.read().strip()
            
            if pid_str.isdigit():
                lock_pid = int(pid_str)
                current_pid = os.getpid()
                
                if lock_pid != current_pid and psutil.pid_exists(lock_pid):
                    try:
                        process = psutil.Process(lock_pid)
                        process.terminate()
                        process.wait(timeout=3)
                        logger.info(f"Process {lock_pid} terminated")
                    except Exception as e:
                        logger.error(f"Failed to terminate process {lock_pid}: {e}")
                        success = False
            
            os.remove(LOCK_FILE)
            logger.info("Lock file removed")
        except Exception as e:
            logger.error(f"Error handling lock file: {e}")
            success = False
    
    if success:
        return jsonify({"message": "Monitoramento encerrado com sucesso!"}), 200
    else:
        return jsonify({"message": "Monitoramento parcialmente encerrado com falhas"}), 500
        
@app.route('/status', methods=['GET'])
@requires_auth
def status():
    """Nova rota para verificar o status do monitoramento"""
    try:
        if is_monitor_running():
            if os.path.exists(LOCK_FILE):
                with open(LOCK_FILE, 'r') as f:
                    pid = f.read().strip()
                return jsonify({
                    "status": "running",
                    "message": f"Monitoramento ativo (PID: {pid})",
                    "is_local": pid == str(os.getpid())
                }), 200
            else:
                return jsonify({
                    "status": "unknown",
                    "message": "Status inconsistente"
                }), 500
        else:
            return jsonify({
                "status": "stopped",
                "message": "Nenhum monitoramento ativo"
            }), 200
    except Exception as e:
        get_logger().error(f"Erro ao verificar status: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Erro ao verificar status: {str(e)}"
        }), 500

@app.route('/logs')
@requires_auth
def logs():
    try:
        log_file_path = os.path.join(LOGS_DIR, 'app.log')
        if not os.path.exists(log_file_path):
            get_logger().error("Arquivo de log não encontrado")
            return jsonify({"message": "Arquivo de log não encontrado"}), 404
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        get_logger().debug("Logs acessados via /logs")
        return Response(content, mimetype='text/plain')
    except Exception as e:
        get_logger().error(f"Erro ao ler logs: {str(e)}")
        return jsonify({"message": f"Erro ao ler logs: {str(e)}"}), 500

# @app.route('/archive_log', methods=['GET'])
# @requires_auth
# def archive_log():
#     try:
#         logger = get_logger()
#         gmt_minus_3 = timezone(timedelta(hours=-3))
#         timestamp = datetime.now(gmt_minus_3).strftime("%Y-%m-%d_%H-%M-%S")
#         log_file_path = os.path.join(LOGS_DIR, 'app.log')
        
#         for handler in logger.handlers:
#             if isinstance(handler, ConcurrentRotatingFileHandler):
#                 handler.close()
#                 if os.path.exists(log_file_path):
#                     archived_name = f"{log_file_path}.{timestamp}"
#                     os.rename(log_file_path, archived_name)
#                 open(log_file_path, 'a').close()  # Cria novo arquivo vazio
#                 new_handler = ConcurrentRotatingFileHandler(
#                     log_file_path,
#                     maxBytes=10**10,
#                     backupCount=7,
#                     encoding='utf-8'
#                 )
#                 formatter = GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s')
#                 new_handler.setFormatter(formatter)
#                 logger.removeHandler(handler)
#                 logger.addHandler(new_handler)
#                 logger.info(f"Log rotacionado para {archived_name}")
#         return jsonify({"message": "Log arquivado com sucesso"}), 200
#     except Exception as e:
#         get_logger().error(f"Erro ao arquivar log: {str(e)}")
#         return jsonify({"error": str(e)}), 500
@app.route('/archive_log', methods=['GET'])
@requires_auth
def archive_log():
    """Força a rotação do log atual via HTTP."""
    try:
        if force_log_rotation():
            return jsonify({"message": "Log rotacionado com sucesso"}), 200
        else:
            return jsonify({"message": "Falha ao rotacionar log: nenhum handler de arquivo ou modo de teste ativo"}), 400
    except Exception as e:
        get_logger().error(f"Erro ao rotacionar log: {str(e)}")
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
        return jsonify({"message": f"Erro ao baixar logs: {str(e)}"}), 500

@app.route('/download-hash-file', methods=['GET'])
@requires_auth
def download_hash_file():
    data_dir = os.path.join(os.path.expanduser("~"), ".marketroxo_data")
    hash_file_path = os.path.join(data_dir, "seen_ads.txt")
    
    if not os.path.exists(hash_file_path):
        get_logger().error("Arquivo hash não encontrado")
        return jsonify({"message": "Arquivo hash não encontrado"}), 404
    
    get_logger().info("Arquivo hash baixado via /download-hash-file")
    return send_file(hash_file_path, as_attachment=True)

@app.route('/health', methods=['GET'])
@requires_auth
def health_check():
    """Endpoint de health check com estatísticas de requests"""
    try:
        monitor = get_monitor_instance()
        
        if monitor is None:
            return jsonify({
                'status': 'error',
                'message': 'Monitor não inicializado',
                'stats': None
            }), 500
        
        # Obtém estatísticas do monitor
        health_stats = monitor.get_health_stats()
        
        # Adiciona informações do status do monitor
        health_stats['monitor_status'] = {
            'is_running': monitor.is_running,
            'thread_alive': monitor.thread.is_alive() if monitor.thread else False
        }
        
        # Determina o status geral
        overall_stats = health_stats['overall']
        success_rate = overall_stats.get('success_rate', 0)
        
        if success_rate >= 80:
            status = 'healthy'
        elif success_rate >= 60:
            status = 'warning'
        else:
            status = 'critical'
        
        return jsonify({
            'status': status,
            'success_rate': success_rate,
            'message': f'Taxa de sucesso: {success_rate}%',
            'stats': health_stats
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erro ao obter estatísticas: {str(e)}',
            'stats': None
        }), 500

@app.route('/health/stats', methods=['GET'])
@requires_auth
def detailed_stats():
    """Endpoint com estatísticas detalhadas"""
    try:
        monitor = get_monitor_instance()
        
        if monitor is None:
            return jsonify({
                'error': 'Monitor não inicializado'
            }), 500
        
        return jsonify(monitor.get_health_stats()), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Erro ao obter estatísticas: {str(e)}'
        }), 500

@app.route('/health/export', methods=['POST'])
@requires_auth
def export_stats():
    """Endpoint para exportar estatísticas"""
    try:
        monitor = get_monitor_instance()
        
        if monitor is None:
            return jsonify({
                'error': 'Monitor não inicializado'
            }), 500
        
        # Exporta estatísticas
        export_file = monitor.stats.export_stats()
        
        if export_file:
            return jsonify({
                'message': 'Estatísticas exportadas com sucesso',
                'file': export_file
            }), 200
        else:
            return jsonify({
                'error': 'Falha ao exportar estatísticas'
            }), 500
            
    except Exception as e:
        return jsonify({
            'error': f'Erro ao exportar estatísticas: {str(e)}'
        }), 500

@app.route('/health/reset', methods=['POST'])
@requires_auth
def reset_stats():
    """Endpoint para resetar estatísticas (use com cuidado!)"""
    try:
        monitor = get_monitor_instance()
        
        if monitor is None:
            return jsonify({
                'error': 'Monitor não inicializado'
            }), 500
        
        # Reseta estatísticas
        monitor.stats.reset_stats()
        
        return jsonify({
            'message': 'Estatísticas resetadas com sucesso'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Erro ao resetar estatísticas: {str(e)}'
        }), 500

# Função de limpeza para quando a aplicação é encerrada
def cleanup():
    """Limpa recursos quando a aplicação é encerrada"""
    global monitor
    if monitor and monitor.is_running:
        get_logger().info("Encerrando monitoramento durante cleanup...")
        monitor.stop()
    release_lock()

import atexit
atexit.register(cleanup)

if __name__ == '__main__':
    get_logger().info("Aplicação iniciada - Market Roxo Monitor")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=False, processes=1)