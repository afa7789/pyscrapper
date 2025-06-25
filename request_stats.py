import os
import json
from collections import deque, defaultdict
from datetime import datetime, timezone
from logging_config import get_logger

class RequestStats:
    """Classe para gerenciar estatísticas de requests por conjunto de palavras-chave"""
    
    def __init__(self, stats_file=None, max_history=1000):
        self.max_history = max_history
        self.logger = get_logger()
        
        # Arquivo para salvar estatísticas
        if stats_file is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".marketroxo_data")
            os.makedirs(data_dir, exist_ok=True)
            self.stats_file = os.path.join(data_dir, "request_stats.json")
            self.logger.info(f"📊 Usando arquivo de estatísticas: {self.stats_file}")
        else:
            self.stats_file = stats_file
            
        # Contadores por conjunto de palavras-chave
        self.success_counters = defaultdict(int)
        self.error_counters = defaultdict(int)
        
        # Histórico dos últimos N requests (deque para performance)
        self.request_history = deque(maxlen=self.max_history)
        
        # Carrega dados existentes
        self._load_stats()
        
    def _get_keyword_set_key(self, keywords):
        """Converte conjunto de palavras-chave em string chave"""
        if isinstance(keywords, (list, tuple)):
            return "|".join(sorted(keywords))
        return str(keywords)
    
    def _load_stats(self):
        """Carrega estatísticas do arquivo"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Carrega contadores
                self.success_counters = defaultdict(int, data.get('success_counters', {}))
                self.error_counters = defaultdict(int, data.get('error_counters', {}))
                
                # Carrega histórico (converte de lista para deque)
                history_data = data.get('request_history', [])
                self.request_history = deque(history_data, maxlen=self.max_history)
                
                total_success = sum(self.success_counters.values())
                total_errors = sum(self.error_counters.values())
                self.logger.info(f"📊 Estatísticas carregadas: {total_success} sucessos, {total_errors} erros, histórico de {len(self.request_history)} requests")
        except Exception as e:
            self.logger.error(f"❌ Erro ao carregar estatísticas: {str(e)}")
    
    def _save_stats(self):
        """Salva estatísticas no arquivo"""
        try:
            data = {
                'success_counters': dict(self.success_counters),
                'error_counters': dict(self.error_counters),
                'request_history': list(self.request_history),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar estatísticas: {str(e)}")
    
    def record_success(self, keywords, page_num=None, ads_found=0):
        """Registra um request bem-sucedido"""
        keyword_key = self._get_keyword_set_key(keywords)
        self.success_counters[keyword_key] += 1
        
        # Adiciona ao histórico
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'keywords': keyword_key,
            'status': 'success',
            'page': page_num,
            'ads_found': ads_found
        }
        self.request_history.append(record)
        
        self.logger.info(f"✅ Sucesso registrado para '{keyword_key}' (página {page_num}, {ads_found} anúncios)")
        self._save_stats()
    
    def record_error(self, keywords, page_num=None, error_type=None, error_message=None):
        """Registra um request com erro"""
        keyword_key = self._get_keyword_set_key(keywords)
        self.error_counters[keyword_key] += 1
        
        # Adiciona ao histórico
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'keywords': keyword_key,
            'status': 'error',
            'page': page_num,
            'error_type': error_type,
            'error_message': error_message[:200] if error_message else None  # Limita tamanho da mensagem
        }
        self.request_history.append(record)
        
        self.logger.warning(f"❌ Erro registrado para '{keyword_key}' (página {page_num}): {error_type}")
        self._save_stats()
    
    def get_stats_by_keyword_set(self, keywords=None):
        """Retorna estatísticas para um conjunto específico ou todos"""
        if keywords:
            keyword_key = self._get_keyword_set_key(keywords)
            success = self.success_counters.get(keyword_key, 0)
            errors = self.error_counters.get(keyword_key, 0)
            total = success + errors
            success_rate = (success / total * 100) if total > 0 else 0
            
            return {
                'keyword_set': keyword_key,
                'success_count': success,
                'error_count': errors,
                'total_requests': total,
                'success_rate': round(success_rate, 2)
            }
        else:
            # Retorna stats de todos os conjuntos
            all_sets = set(list(self.success_counters.keys()) + list(self.error_counters.keys()))
            return {keyword_set: self.get_stats_by_keyword_set(keyword_set.split('|')) 
                   for keyword_set in all_sets}
    
    def get_overall_stats(self):
        """Retorna estatísticas gerais dos últimos N requests"""
        if not self.request_history:
            return {
                'total_requests': 0,
                'success_count': 0,
                'error_count': 0,
                'success_rate': 0,
                'history_size': 0,
                'max_history': self.max_history
            }
        
        # Analisa apenas o histórico recente (últimos max_history requests)
        recent_requests = list(self.request_history)
        success_count = sum(1 for r in recent_requests if r['status'] == 'success')
        error_count = sum(1 for r in recent_requests if r['status'] == 'error')
        total = len(recent_requests)
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        return {
            'total_requests': total,
            'success_count': success_count,
            'error_count': error_count,
            'success_rate': round(success_rate, 2),
            'history_size': len(self.request_history),
            'max_history': self.max_history
        }
    
    def get_recent_errors(self, limit=10):
        """Retorna os erros mais recentes"""
        recent_errors = [r for r in reversed(self.request_history) if r['status'] == 'error']
        return recent_errors[:limit]
    
    def get_stats_summary(self):
        """Retorna um resumo completo das estatísticas"""
        overall = self.get_overall_stats()
        by_keyword = self.get_stats_by_keyword_set()
        recent_errors = self.get_recent_errors(5)
        
        return {
            'overall': overall,
            'by_keyword_set': by_keyword,
            'recent_errors': recent_errors,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def reset_stats(self):
        """Reseta todas as estatísticas (use com cuidado!)"""
        self.success_counters.clear()
        self.error_counters.clear()
        self.request_history.clear()
        self._save_stats()
        self.logger.warning("⚠️ Todas as estatísticas foram resetadas!")
    
    def export_stats(self, export_file=None):
        """Exporta estatísticas para um arquivo específico"""
        if export_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = f"stats_export_{timestamp}.json"
        
        try:
            stats_data = self.get_stats_summary()
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"📤 Estatísticas exportadas para: {export_file}")
            return export_file
        except Exception as e:
            self.logger.error(f"❌ Erro ao exportar estatísticas: {str(e)}")
            return None