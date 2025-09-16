import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from concurrent_log_handler import ConcurrentRotatingFileHandler
from datetime import datetime, timezone, timedelta
import threading
import time
import glob
import atexit

class GMT3Formatter(logging.Formatter):
    def converter(self, timestamp):
        gmt_minus_3 = timezone(timedelta(hours=-3))
        return datetime.fromtimestamp(timestamp, gmt_minus_3)

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")  # Removed %Z timezone

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Handler customizado para rotação por tempo com timezone GMT-3"""
    
    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc)
        self.utc = False
    
    def computeRollover(self, currentTime):
        gmt_minus_3 = timezone(timedelta(hours=-3))
        current_dt = datetime.fromtimestamp(currentTime, gmt_minus_3)
        
        if self.when == 'H' or self.when.startswith('h'):
            next_hour = current_dt.replace(minute=0, second=0, microsecond=0)
            next_hour += timedelta(hours=self.interval)
            return next_hour.timestamp()
        
        return super().computeRollover(currentTime)

class LogRotationManager:
    def __init__(self, log_dir='logs', max_log_files=50):
        self.log_dir = log_dir
        self.max_log_files = max_log_files
        self.cleanup_thread = None
        self.running = False
    
    def start_cleanup_monitor(self):
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger = logging.getLogger('marketroxo')
        logger.info(f"🧹 Monitor de limpeza de logs iniciado (máx: {self.max_log_files} arquivos)")
    
    def stop_cleanup_monitor(self):
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=1)
    
    def _cleanup_loop(self):
        while self.running:
            try:
                self.cleanup_old_logs()
                time.sleep(3600)
            except Exception as e:
                logger = logging.getLogger('marketroxo')
                logger.error(f"Erro no monitor de limpeza: {e}")
                time.sleep(300)
    
    def cleanup_old_logs(self):
        try:
            if not os.path.exists(self.log_dir):
                return
            
            log_pattern = os.path.join(self.log_dir, "app.log*")
            log_files = glob.glob(log_pattern)
            
            if len(log_files) <= self.max_log_files:
                return
            
            log_files.sort(key=os.path.getmtime)
            
            files_to_remove = len(log_files) - self.max_log_files
            removed_count = 0
            
            for log_file in log_files[:files_to_remove]:
                try:
                    if log_file.endswith('app.log') and not any(c.isdigit() for c in log_file.split('.')[-1]):
                        continue
                    
                    os.remove(log_file)
                    removed_count += 1
                except OSError:
                    pass
            
            if removed_count > 0:
                logger = logging.getLogger('marketroxo')
                logger.info(f"🧹 Removidos {removed_count} arquivos de log antigos")
        
        except Exception as e:
            logger = logging.getLogger('marketroxo')
            logger.error(f"Erro na limpeza de logs: {e}")

_rotation_manager = LogRotationManager()

def setup_logging(rotation_type='size', rotation_interval=4):
    logger = logging.getLogger('marketroxo')
    logger.setLevel(logging.INFO)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    is_test_mode = os.getenv('TEST_MODE', '0') == '1'

    if is_test_mode:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        os.makedirs('logs', exist_ok=True)
        
        if rotation_type == 'time':
            handler = CustomTimedRotatingFileHandler(
                'logs/app.log',
                when='h',
                interval=rotation_interval,
                backupCount=24,
                encoding='utf-8'
            )
            logger.info(f"🔄 Configurado rotação por tempo: a cada {rotation_interval} horas")
        else:
            max_bytes = rotation_interval * 1024 * 1024
            # ConcurrentRotatingFileHandler is process-safe for multiple workers
            handler = ConcurrentRotatingFileHandler(
                'logs/app.log',
                maxBytes=max_bytes,
                backupCount=20,
                encoding='utf-8',
                use_gzip=False  # Disable gzip to avoid conflicts
            )
            logger.info(f"🔄 Configurado rotação por tamanho: a cada {rotation_interval}MB")
        
        _rotation_manager.start_cleanup_monitor()
        
        formatter = GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)

def setup_frequent_rotation():
    setup_logging(rotation_type='size', rotation_interval=10)

def setup_hourly_rotation():
    setup_logging(rotation_type='time', rotation_interval=1)

def setup_4hour_rotation():
    """Setup 4-hour log rotation with process-safe handling"""
    setup_logging(rotation_type='time', rotation_interval=4)

def get_logger():
    """Retorna o logger configurado, reinicializando se necessário."""
    logger = logging.getLogger('marketroxo')
    signal_file = os.path.join('logs', 'rotation_signal')
    
    # Sempre verifica se precisa reinicializar após rotação
    if os.path.exists(signal_file):
        try:
            with open(signal_file, 'r') as f:
                timestamp = f.read().strip()
            os.remove(signal_file)
            
            # Remove handlers antigos
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            
            # Reconfigura logging completamente
            setup_4hour_rotation()
            logger.info(f"🔄 Logger reinicializado após rotação ({timestamp}) - PID: {os.getpid()}")
            
        except Exception as e:
            print(f"Erro ao reinicializar logger: {e}")
    
    # Se não tem handlers, configura automaticamente
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        is_test_mode = os.getenv('TEST_MODE', '0') == '1'
        
        if is_test_mode:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '[%(asctime)s] %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        else:
            # Configura handler de arquivo
            os.makedirs('logs', exist_ok=True)
            log_file_path = os.path.join('logs', 'app.log')
            
            # Usa ConcurrentRotatingFileHandler por ser mais confiável em multi-process
            handler = ConcurrentRotatingFileHandler(
                log_file_path,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=20,
                encoding='utf-8',
                use_gzip=False
            )
            handler.setFormatter(GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s'))
            logger.addHandler(handler)
        
        logger.info(f"🔧 Logger configurado automaticamente - PID: {os.getpid()}")
    
    return logger

def force_log_rotation():
    """Força a rotação do log atual, arquivando com timestamp."""
    logger = logging.getLogger('marketroxo')
    log_file_path = os.path.join('logs', 'app.log')
    gmt_minus_3 = timezone(timedelta(hours=-3))
    timestamp = datetime.now(gmt_minus_3).strftime("%Y-%m-%d_%H-%M-%S")
    
    is_test_mode = os.getenv('TEST_MODE', '0') == '1'
    if is_test_mode:
        logger.warning("Rotação de log não suportada em modo de teste")
        return False
    
    rotated = False
    handlers = logger.handlers[:]
    
    for handler in handlers:
        try:
            if isinstance(handler, (ConcurrentRotatingFileHandler, CustomTimedRotatingFileHandler)):
                handler.flush()
                handler.close()
            logger.removeHandler(handler)
        except Exception as e:
            logger.error(f"Erro ao fechar handler: {e}")
    
    try:
        if os.path.exists(log_file_path):
            archived_name = f"{log_file_path}.{timestamp}"
            os.rename(log_file_path, archived_name)
            logger.info(f"🔄 Log rotacionado para {archived_name}")
            os.sync()
        open(log_file_path, 'a').close()
        rotated = True
    except Exception as e:
        logger.error(f"Erro ao renomear ou criar novo arquivo de log: {e}")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(console_handler)
        return False
    
    try:
        new_handler = CustomTimedRotatingFileHandler(
            log_file_path,
            when='h',
            interval=4,
            backupCount=24,
            encoding='utf-8'
        )
        new_handler.setFormatter(GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s'))
        logger.addHandler(new_handler)
        logger.info("🔄 Novo handler de log configurado após rotação")
        
        # Cria sinal de rotação para notificar todos os workers
        signal_file = os.path.join('logs', 'rotation_signal')
        with open(signal_file, 'w') as f:
            f.write(timestamp)
        
        # Força todos os workers a recarregar handlers na próxima chamada get_logger()
        import signal
        import subprocess
        try:
            # Envia SIGUSR1 para todos os workers do gunicorn para forçar reload
            subprocess.run(['pkill', '-SIGUSR1', '-f', 'gunicorn'], check=False)
            logger.info("📢 Sinal de rotação enviado para todos os workers")
        except Exception as e:
            logger.warning(f"Aviso: não foi possível sinalizar workers: {e}")
        
        return rotated
    except Exception as e:
        logger.error(f"Erro ao configurar novo handler: {e}")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(console_handler)
        return False

def cleanup_on_exit():
    global _rotation_manager
    _rotation_manager.stop_cleanup_monitor()

def log_debug(message):
    get_logger().debug(message)

def log_info(message):
    get_logger().info(message)

def log_error(message):
    get_logger().error(message)

def log_warning(message):
    get_logger().warning(message)

atexit.register(cleanup_on_exit)