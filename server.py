from flask import Flask, Response, request, render_template
from functools import wraps
import logging
import os
from dotenv import load_dotenv
import json
from threading import Thread
from monitor import Monitor
from scraper_cloudflare import MarketRoxoScraperCloudflare
from telegram_bot import TelegramBot

app = Flask(__name__, template_folder='template')

# Configuração de logging
logging.basicConfig(
    filename='app.log',
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname).1s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_INPUT = os.getenv("TELEGRAM_CHAT_ID_OR_PHONE", "")

DEFAULT_KEYWORDS = os.getenv("DEFAULT_KEYWORDS", "iphone, samsung, xiaomi")
NEGATIVE_KEYWORDS = os.getenv("NEGATIVE_KEYWORDS_LIST", "")

BASE_URL = os.getenv("MAIN_URL_SCRAPE_ROXO", "")
if not BASE_URL:
    logger.error(
        "Variável de ambiente MAIN_URL_SCRAPE_ROXO não está definida ou está vazia.")
    raise ValueError(
        "Variável de ambiente MAIN_URL_SCRAPE_ROXO não está definida ou está vazia.")

# Credenciais para Basic Auth
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

# Instância global do Monitor
monitor = None
monitor_thread = None

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

def check_auth(username, password):
    """Verifica as credenciais do Basic Auth."""
    return username == USERNAME and password == PASSWORD

def authenticate():
    """Resposta para autenticação não autorizada."""
    return Response(
        'Autenticação necessária.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    """Decorador para rotas protegidas por Basic Auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

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
    return render_template(
        'admin.html',
        keywords_list=DEFAULT_KEYWORDS,
        negative_keywords_list=NEGATIVE_KEYWORDS,
        token=TELEGRAM_TOKEN,
        chat_input=CHAT_INPUT,
        username=USERNAME,
        password=PASSWORD
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
        keywords_list = [kw.strip() for kw in data['keywords_list'].split(",") if kw.strip()]
        negative_keywords_list = [
            kw.strip() for kw in data['negative_keywords_list'].split(",") if kw.strip()]
        token = data['token']
        chat_input = data['chat_input']

        telegram_bot = TelegramBot(log_callback=logger.info, token=token)
        # proxy = PROXIES.get("https") or PROXIES.get("http") or None
        # if proxy and ("http://" in proxy or "https://" in proxy):
        #     proxy = proxy.replace("http://", "").replace("https://", "")
        scraper = MarketRoxoScraperCloudflare(
            log_callback=logger.info, 
            base_url=BASE_URL, 
            proxies=PROXIES,
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
    """Retorna o conteúdo do arquivo de log."""
    try:
        with open('app.log', 'r', encoding='utf-8') as f:
            log_content = f.read()
        return Response(log_content, mimetype='text/plain')
    except Exception as e:
        logger.error(f"Erro ao ler logs: {str(e)}")
        return {"message": f"Erro ao ler logs: {str(e)}"}, 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=False, processes=1)