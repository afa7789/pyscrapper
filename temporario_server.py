import os
import fcntl
import psutil
from flask import Flask, Response, request, jsonify
from monitor import Monitor
from logging_config import get_logger

app = Flask(__name__, template_folder='template')
monitor = None
LOCK_FILE = 'monitor.lock'

def acquire_lock():
    """Tenta adquirir o lock file e armazena o PID do processo atual"""
    try:
        lock_file = open(LOCK_FILE, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        pid = os.getpid()
        lock_file.write(str(pid))
        lock_file.flush()
        get_logger().info(f"Lock adquirido pelo processo {pid}")
        return lock_file
    except IOError:
        lock_file.close()
        return None

def release_lock(lock_file):
    """Libera o lock file"""
    if lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
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
            pid_str = int(f.read().strip()
            if pid and int(pid_str):
                return psutil.pid_exists(int(pid_str))
    except (ValueError, OSError, IOError):
        return False
    return True

@app.route('/stop', methods=['POST'])
@requires_auth
def stop():
    global monitor
    logger = get_logger()
    
    if not is_monitor_running():
        logger.info("Nenhum monitoramento ativo detectado")
        return jsonify({"message": "error: Nenhum monitoramento ativo"}), 400
    
    try:
        with open(LOCK_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        if pid == os.getpid() and monitor and monitor.is_running:
            success = monitor.stop()
            if success:
                logger.info("Monitoramento encerrado com sucesso")
                monitor = None
                lock_file = acquire_lock()  # Reacquire to release cleanly
                if lock_file:
                    release_lock(lock_file)
                return jsonify({"message": "Monitoramento encerrado com sucesso!"}), 200
            else:
                logger.warning("Falha ao encerrar monitoramento")
                return jsonify({"message": "Falha ao encerrar monitoramento, tente novamente"}), 500
        else:
            if not psutil.pid_exists(pid):
                logger.info("Processo monitor não existe mais, limpando lock")
                if os.path.exists(LOCK_FILE):
                    os.remove(LOCK_FILE)
                return jsonify({"message": "Monitoramento inativo, lock limpo"}), 200
            logger.info("Monitoramento ativo em outro processo")
            return jsonify({"message": "Monitoramento ativo em outro processo, tente novamente"}), 400
    except Exception as e:
        logger.error(f"Erro ao encerrar monitoramento: {str(e)}")
        return jsonify({"message": f"Erro ao encerrar: {str(e)}"}), 500