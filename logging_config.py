import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from concurrent_log_handler import ConcurrentRotatingFileHandler
from datetime import datetime, timezone, timedelta
import threading
import time
import glob
# Registra a função de limpeza para ser executada na saída
import atexit

class GMT3Formatter(logging.Formatter):
    def converter(self, timestamp):
        gmt_minus_3 = timezone(timedelta(hours=-3))
        return datetime.fromtimestamp(timestamp, gmt_minus_3)

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Handler customizado para rotação por tempo com timezone GMT-3"""
    
    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc)
        # Força o uso do timezone GMT-3
        self.utc = False
    
    def computeRollover(self, currentTime):
        """Calcula o próximo momento de rotação usando GMT-3"""
        gmt_minus_3 = timezone(timedelta(hours=-3))
        current_dt = datetime.fromtimestamp(currentTime, gmt_minus_3)
        
        if self.when == 'H' or self.when.startswith('h'):
            # Rotação a cada X horas
            next_hour = current_dt.replace(minute=0, second=0, microsecond=0)
            next_hour += timedelta(hours=self.interval)
            return next_hour.timestamp()
        
        return super().computeRollover(currentTime)

class LogRotationManager:
    """Gerenciador de rotação de logs"""
    
    def __init__(self, log_dir='logs', max_log_files=50):
        self.log_dir = log_dir
        self.max_log_files = max_log_files
        self.cleanup_thread = None
        self.running = False
    
    def start_cleanup_monitor(self):
        """Inicia o monitor de limpeza de logs antigos"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger = logging.getLogger('marketroxo')
        logger.info(f"🧹 Monitor de limpeza de logs iniciado (máx: {self.max_log_files} arquivos)")
    
    def stop_cleanup_monitor(self):
        """Para o monitor de limpeza"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=1)
    
    def _cleanup_loop(self):
        """Loop de limpeza que roda em background"""
        while self.running:
            try:
                self.cleanup_old_logs()
                # Verifica a cada hora
                time.sleep(3600)
            except Exception as e:
                logger = logging.getLogger('marketroxo')
                logger.error(f"Erro no monitor de limpeza: {e}")
                time.sleep(300)  # Espera 5 minutos em caso de erro
    
    def cleanup_old_logs(self):
        """Remove logs antigos mantendo apenas os mais recentes"""
        try:
            if not os.path.exists(self.log_dir):
                return
            
            # Busca todos os arquivos de log
            log_pattern = os.path.join(self.log_dir, "app.log*")
            log_files = glob.glob(log_pattern)
            
            if len(log_files) <= self.max_log_files:
                return
            
            # Ordena por data de modificação (mais antigos primeiro)
            log_files.sort(key=os.path.getmtime)
            
            # Remove os mais antigos
            files_to_remove = len(log_files) - self.max_log_files
            removed_count = 0
            
            for log_file in log_files[:files_to_remove]:
                try:
                    # Não remove o arquivo principal app.log
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

# Instância global do gerenciador
_rotation_manager = LogRotationManager()

def setup_logging(rotation_type='size', rotation_interval=4):
    """
    Configura o logging com rotação automática.
    
    Args:
        rotation_type: 'size' para rotação por tamanho, 'time' para rotação por tempo
        rotation_interval: Para 'time': horas entre rotações. Para 'size': MB por arquivo
    """
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
        # Em modo de produção, escolhe o tipo de rotação
        os.makedirs('logs', exist_ok=True)
        
        if rotation_type == 'time':
            # Rotação por tempo (a cada X horas)
            handler = CustomTimedRotatingFileHandler(
                'logs/app.log',
                when='h',
                interval=rotation_interval,
                backupCount=24,  # Mantém 24 arquivos (1 dia com rotação de 1h, ou 4 dias com rotação de 4h)
                encoding='utf-8'
            )
            logger.info(f"🔄 Configurado rotação por tempo: a cada {rotation_interval} horas")
            
        else:
            # Rotação por tamanho (padrão melhorado)
            max_bytes = rotation_interval * 1024 * 1024  # Converte MB para bytes
            handler = ConcurrentRotatingFileHandler(
                'logs/app.log',
                maxBytes=max_bytes,
                backupCount=20,  # Mantém 20 arquivos de backup
                encoding='utf-8'
            )
            logger.info(f"🔄 Configurado rotação por tamanho: a cada {rotation_interval}MB")
        
        # Inicia o monitor de limpeza
        _rotation_manager.start_cleanup_monitor()
        
        formatter = GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)

def setup_frequent_rotation():
    """Configuração pré-definida para rotação frequente"""
    setup_logging(rotation_type='size', rotation_interval=10)  # 10MB por arquivo

def setup_hourly_rotation():
    """Configuração pré-definida para rotação de hora em hora"""
    setup_logging(rotation_type='time', rotation_interval=1)  # A cada 1 hora

def setup_4hour_rotation():
    """Configuração pré-definida para rotação de 4 em 4 horas"""
    setup_logging(rotation_type='time', rotation_interval=4)  # A cada 4 horas

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
    
def force_log_rotation():
    """Força a rotação do log atual, arquivando com timestamp."""
    logger = logging.getLogger('marketroxo')
    log_file_path = os.path.join('logs', 'app.log')
    gmt_minus_3 = timezone(timedelta(hours=-3))
    timestamp = datetime.now(gmt_minus_3).strftime("%Y-%m-%d_%H-%M-%S")
    
    # Verifica se está em modo de teste
    is_test_mode = os.getenv('TEST_MODE', '0') == '1'
    if is_test_mode:
        logger.warning("Rotação de log não suportada em modo de teste")
        return False
    
    rotated = False
    # Cria uma cópia da lista de handlers para evitar modificação durante iteração
    handlers = logger.handlers[:]
    # Remove todos os handlers existentes para evitar duplicatas
    for handler in handlers:
        logger.removeHandler(handler)
        if isinstance(handler, (ConcurrentRotatingFileHandler, CustomTimedRotatingFileHandler)):
            try:
                # Força flush e fecha o handler
                handler.flush()
                handler.close()
            except Exception as e:
                logger.error(f"Erro ao fechar handler: {e}")
    
    # Renomeia o arquivo de log atual, se existir
    try:
        if os.path.exists(log_file_path):
            archived_name = f"{log_file_path}.{timestamp}"
            os.rename(log_file_path, archived_name)
            logger.info(f"🔄 Log rotacionado para {archived_name}")
        # Cria um novo arquivo de log vazio
        open(log_file_path, 'a').close()
        rotated = True
    except Exception as e:
        logger.error(f"Erro ao renomear ou criar novo arquivo de log: {e}")
        # Re-adiciona um handler de console temporário se a rotação falhar
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(console_handler)
        return False
    
    # Cria um novo handler com a configuração apropriada
    try:
        # Determina o tipo de handler com base na configuração anterior
        for handler in handlers:
            if isinstance(handler, ConcurrentRotatingFileHandler):
                new_handler = ConcurrentRotatingFileHandler(
                    log_file_path,
                    maxBytes=handler.maxBytes,
                    backupCount=handler.backupCount,
                    encoding='utf-8'
                )
                new_handler.setFormatter(handler.formatter)
                logger.addHandler(new_handler)
                break
            elif isinstance(handler, CustomTimedRotatingFileHandler):
                new_handler = CustomTimedRotatingFileHandler(
                    log_file_path,
                    when=handler.when, # Declare a variável `when` para evitar conflito com a palavra-chave.
                    interval=handler.interval,
                    backupCount=handler.backupCount,
                    encoding='utf-8'
                )
                new_handler.setFormatter(handler.formatter)
                logger.addHandler(new_handler)
                break
        else:
            # Configura um handler padrão se não houver correspondência
            new_handler = ConcurrentRotatingFileHandler(
                log_file_path,
                maxBytes=10 * 1024 * 1024,  # 10MB padrão
                backupCount=20,
                encoding='utf-8'
            )
            new_handler.setFormatter(GMT3Formatter('%(asctime)s - %(levelname).1s - %(message)s'))
            logger.addHandler(new_handler)
        
        logger.info("🔄 Novo handler de log configurado após rotação")
        return rotated
    except Exception as e:
        logger.error(f"Erro ao configurar novo handler: {e}")
        # Re-adiciona um handler de console em caso de erro
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(console_handler)
        return False
        
def cleanup_on_exit():
    """Função para limpar recursos na saída"""
    global _rotation_manager
    _rotation_manager.stop_cleanup_monitor()

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

# Registra a função de limpeza para ser executada na saída
atexit.register(cleanup_on_exit)
