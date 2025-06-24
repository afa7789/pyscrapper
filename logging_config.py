import logging
import os
from logging.handlers import RotatingFileHandler
from concurrent_log_handler import ConcurrentRotatingFileHandler
from datetime import datetime, timezone, timedelta

class GMT3Formatter(logging.Formatter):
    def converter(self, timestamp):
        gmt_minus_3 = timezone(timedelta(hours=-3))
        return datetime.fromtimestamp(timestamp, gmt_minus_3)

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

def setup_logging():
    """Configura o logging com base no ambiente (teste ou produção)."""
    logger = logging.getLogger('marketroxo')
    logger.setLevel(logging.INFO)

    # Remove quaisquer handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Verifica se está em modo de teste via variável de ambiente
    is_test_mode = os.getenv('TEST_MODE', '0') == '1'

    if is_test_mode:
        # Em modo de teste, usa StreamHandler para imprimir no console
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        # Em modo de produção, usa ConcurrentRotatingFileHandler
        os.makedirs('logs', exist_ok=True)
        handler = ConcurrentRotatingFileHandler(
            'logs/app.log',
            maxBytes=10**10,
            backupCount=7,
            encoding='utf-8'
        )
        formatter = GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)

def get_logger():
    """Retorna o logger configurado. Se não estiver configurado, configura automaticamente para console."""
    logger = logging.getLogger('marketroxo')
    
    # Se o logger não tem handlers, configura um handler de console automaticamente
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Cria handler de console
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # Log de inicialização automática
        logger.info("🔧 Logger configurado automaticamente para console")
    
    return logger

def log_debug(message):
    """Função de conveniência para log de debug"""
    get_logger().debug(message)

def log_info(message):
    """Função de conveniência para log de info"""
    get_logger().info(message)

def log_error(message):
    """Função de conveniência para log de erro"""
    get_logger().error(message)

def log_warning(message):
    """Função de conveniência para log de warning"""
    get_logger().warning(message)